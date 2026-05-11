"""Phase 6E — Live-Eval Harness CLI with opt-in /api/generate adapter.

Without ``NEXUS_RUN_LIVE_EVAL=true`` in the environment this script
**refuses** to make any real generation calls and exits non-zero. This is
the guard that keeps live evaluation out of the normal backend test gate.

Live evaluation is a thin orchestration layer:

1. POST to ``/api/generate`` with the prompt as ``topic``.
2. Poll ``/api/slides/{task_id}`` until 200 (done), failure, or timeout.
3. Shape the response into the deck dict expected by
   :func:`services.eval_service.evaluate_deck`.
4. Write one JSON record per prompt under
   ``backend/storage/evals/`` (or ``$NEXUS_EVAL_OUTPUT_DIR``).

Network calls happen only via the injectable ``HttpClient`` protocol so
tests can exercise the orchestration without real HTTP.

Usage::

    # Refuse — no env flag:
    python -m scripts.run_live_eval --prompt-id biz-001
    # Real run — explicit opt-in:
    NEXUS_RUN_LIVE_EVAL=true python -m scripts.run_live_eval \\
        --prompt-id biz-001 --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from services.eval_service import evaluate_deck, get_prompt_spec, load_prompts


DEFAULT_TIMEOUT_SECONDS = 600
DEFAULT_POLL_INTERVAL_SECONDS = 3.0


class HttpResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...


class HttpClient(Protocol):
    def post(self, url: str, *, json: dict[str, Any], timeout: float) -> HttpResponse: ...

    def get(self, url: str, *, timeout: float) -> HttpResponse: ...

    def close(self) -> None: ...


def _output_dir() -> Path:
    base = Path(os.environ.get("NEXUS_EVAL_OUTPUT_DIR") or "/app/storage/evals")
    base.mkdir(parents=True, exist_ok=True)
    return base


def _refuse_if_not_opted_in() -> None:
    flag = (os.environ.get("NEXUS_RUN_LIVE_EVAL") or "").strip().lower()
    if flag != "true":
        sys.stderr.write(
            "[run_live_eval] refusing to run: NEXUS_RUN_LIVE_EVAL is not set to 'true'.\n"
            "                  Set NEXUS_RUN_LIVE_EVAL=true to opt in to live calls.\n"
        )
        raise SystemExit(2)


def _build_default_client() -> HttpClient:  # pragma: no cover - real network
    import httpx

    return httpx.Client()  # type: ignore[return-value]


class LiveGenerationError(RuntimeError):
    """Raised for non-recoverable generation failures (HTTP error, task failed)."""


class LiveGenerationTimeout(RuntimeError):
    """Raised when polling exceeds the configured timeout."""


def run_live_generation(
    prompt_text: str,
    *,
    base_url: str,
    theme: str,
    search_web: bool,
    slide_count: int,
    timeout_seconds: float,
    poll_interval_seconds: float,
    client: HttpClient,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
    min_sources: int = 0,
) -> dict[str, Any]:
    """Drive a single end-to-end generate→poll→fetch round-trip.

    Returns a deck dict shaped like ``{"slides": [...], "sources": [...]}``
    suitable for :func:`services.eval_service.evaluate_deck`.

    Pure-orchestration: all HTTP goes through ``client`` so tests can
    inject a fake. The default client is created by ``_build_default_client``.
    """

    base = base_url.rstrip("/")
    payload = {
        "topic": prompt_text,
        "slide_count": int(slide_count),
        "theme": theme,
        "search_web": bool(search_web),
    }
    # Phase 6U: forward expected min_sources so the agent loop's harvest
    # step has an explicit target. Default 0 preserves the prior behaviour.
    if int(min_sources or 0) > 0:
        payload["min_sources"] = int(min_sources)
    create_resp = client.post(f"{base}/api/generate", json=payload, timeout=30.0)
    if create_resp.status_code >= 400:
        raise LiveGenerationError(
            f"POST /api/generate failed: HTTP {create_resp.status_code}"
        )
    body = create_resp.json()
    task_id = body.get("task_id")
    if not task_id:
        raise LiveGenerationError(f"POST /api/generate missing task_id: {body!r}")

    deadline = now() + float(timeout_seconds)
    while True:
        if now() >= deadline:
            raise LiveGenerationTimeout(
                f"task {task_id} did not complete within {timeout_seconds}s"
            )
        resp = client.get(f"{base}/api/slides/{task_id}", timeout=30.0)
        if resp.status_code == 200:
            data = resp.json()
            slides = data.get("slides") or []
            sources = data.get("sources") or []
            return {"slides": slides, "sources": sources, "_task_id": task_id}
        if resp.status_code == 409:
            # Task still pending; /api/slides 409s until status==done. If
            # the task transitions to "failed", /api/slides also 409s with
            # a body.detail mentioning failed — surface that explicitly.
            try:
                detail = resp.json().get("detail", "")
            except Exception:
                detail = ""
            if isinstance(detail, str) and "failed" in detail.lower():
                raise LiveGenerationError(f"task {task_id} failed: {detail}")
            sleep(float(poll_interval_seconds))
            continue
        if resp.status_code == 404:
            raise LiveGenerationError(f"task {task_id} not found")
        raise LiveGenerationError(
            f"GET /api/slides/{task_id} failed: HTTP {resp.status_code}"
        )


def _write_record(record: dict[str, Any]) -> Path:
    out_dir = _output_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"{record['prompt_id']}-{ts}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return path


def main(
    argv: list[str] | None = None,
    *,
    client_factory: Callable[[], HttpClient] | None = None,
    write_record: Callable[[dict[str, Any]], Path] = _write_record,
) -> int:
    parser = argparse.ArgumentParser(description="NEXUS live-eval harness (opt-in).")
    parser.add_argument(
        "--prompt-id",
        required=False,
        help="Run a single prompt id from benchmarks/prompts.json. Omit to run all.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend base URL for /api/generate.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Max wait per prompt before giving up.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="Seconds between /api/slides polls.",
    )
    parser.add_argument(
        "--theme",
        default="Editorial",
        help="Theme to pass to /api/generate.",
    )
    search_group = parser.add_mutually_exclusive_group()
    search_group.add_argument(
        "--search-web",
        dest="search_web",
        action="store_true",
        help="Pass search_web=true to /api/generate (default).",
    )
    search_group.add_argument(
        "--no-search-web",
        dest="search_web",
        action="store_false",
        help="Pass search_web=false to /api/generate.",
    )
    parser.set_defaults(search_web=True)
    parser.add_argument(
        "--slide-count",
        type=int,
        default=8,
        help="slide_count to pass to /api/generate.",
    )
    args = parser.parse_args(argv)

    _refuse_if_not_opted_in()

    prompts = load_prompts()
    if args.prompt_id:
        prompts = [get_prompt_spec(args.prompt_id, prompts)]

    client = (client_factory or _build_default_client)()
    written: list[Path] = []
    failures: list[tuple[str, str]] = []
    try:
        for spec in prompts:
            # Phase 6U: prefer the per-prompt evidence target so each
            # prompt's required source count drives the harvest depth.
            evidence = spec.get("expected_evidence") or {}
            spec_min_sources = 0
            try:
                spec_min_sources = int(evidence.get("min_sources", 0) or 0)
            except (TypeError, ValueError):
                spec_min_sources = 0
            try:
                deck = run_live_generation(
                    spec["prompt"],
                    base_url=args.base_url,
                    theme=args.theme,
                    search_web=args.search_web,
                    slide_count=args.slide_count,
                    timeout_seconds=args.timeout_seconds,
                    poll_interval_seconds=args.poll_interval_seconds,
                    client=client,
                    min_sources=spec_min_sources,
                )
            except (LiveGenerationError, LiveGenerationTimeout) as exc:
                failures.append((spec["id"], str(exc)))
                sys.stderr.write(f"[run_live_eval] {spec['id']} FAILED: {exc}\n")
                continue
            record = evaluate_deck(deck, spec, ran_live=True)
            written.append(write_record(record))
    finally:
        try:
            client.close()
        except Exception:
            pass

    for path in written:
        sys.stdout.write(f"wrote {path}\n")
    if failures:
        sys.stderr.write(
            f"[run_live_eval] {len(failures)} prompt(s) failed: "
            + ", ".join(f"{pid}={err}" for pid, err in failures)
            + "\n"
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
