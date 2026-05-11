"""Phase 6E — Live-Eval CLI adapter tests.

These tests exercise the orchestration in
``backend/scripts/run_live_eval.py`` using an in-memory fake HTTP client
so they make zero real network calls. They never set
``NEXUS_RUN_LIVE_EVAL`` unless the test specifically needs the opt-in
guard to be satisfied.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from scripts import run_live_eval as runner


# ── fake HTTP client ──────────────────────────────────────────────────────


class FakeResponse:
    def __init__(self, status_code: int, body: Any = None) -> None:
        self.status_code = status_code
        self._body = body if body is not None else {}

    def json(self) -> Any:
        return self._body


class FakeClient:
    """In-memory HTTP client. Records calls; returns scripted responses."""

    def __init__(
        self,
        *,
        post_response: FakeResponse,
        get_responses: list[FakeResponse],
    ) -> None:
        self._post_response = post_response
        self._get_responses = list(get_responses)
        self.posts: list[dict[str, Any]] = []
        self.gets: list[str] = []
        self.closed = False

    def post(self, url: str, *, json: dict[str, Any], timeout: float) -> FakeResponse:
        self.posts.append({"url": url, "json": json, "timeout": timeout})
        return self._post_response

    def get(self, url: str, *, timeout: float) -> FakeResponse:
        self.gets.append(url)
        if not self._get_responses:
            raise AssertionError("FakeClient ran out of GET responses")
        return self._get_responses.pop(0)

    def close(self) -> None:
        self.closed = True


_DONE_DECK = {
    "task_id": "tid-abc",
    "topic": "anything",
    "theme": "Editorial",
    "slide_count": 5,
    "slides": [
        {"layout": "title", "title": "T", "subtitle": "S"},
        {"layout": "bullets", "title": "B", "bullets": ["a", "b", "c"]},
        {"layout": "stats", "title": "St", "stats": [{"value": "1", "label": "x"}]},
        {"layout": "two-col", "title": "Tc",
         "left": {"heading": "L", "body": "lb"},
         "right": {"heading": "R", "body": "rb"}},
        {"layout": "closing", "title": "C", "subtitle": "Sub", "cta": "go"},
    ],
    "sources": [],
}


# ── opt-in guard ──────────────────────────────────────────────────────────


def test_main_refuses_without_env_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEXUS_RUN_LIVE_EVAL", raising=False)
    with pytest.raises(SystemExit) as excinfo:
        runner.main(argv=["--prompt-id", "biz-001"])
    assert excinfo.value.code != 0


def test_main_refuses_when_flag_is_not_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_RUN_LIVE_EVAL", "yes")  # not "true"
    with pytest.raises(SystemExit) as excinfo:
        runner.main(argv=["--prompt-id", "biz-001"])
    assert excinfo.value.code != 0


# ── orchestration: post payload ───────────────────────────────────────────


def test_run_live_generation_posts_expected_payload() -> None:
    client = FakeClient(
        post_response=FakeResponse(202, {"task_id": "tid-1", "status": "pending"}),
        get_responses=[FakeResponse(200, _DONE_DECK)],
    )
    deck = runner.run_live_generation(
        "make a deck about X",
        base_url="http://example.test/",
        theme="Editorial",
        search_web=True,
        slide_count=6,
        timeout_seconds=10,
        poll_interval_seconds=0,
        client=client,
        sleep=lambda s: None,
        now=lambda: 0.0,
    )
    assert client.posts[0]["url"] == "http://example.test/api/generate"
    assert client.posts[0]["json"] == {
        "topic": "make a deck about X",
        "slide_count": 6,
        "theme": "Editorial",
        "search_web": True,
    }
    assert deck["_task_id"] == "tid-1"
    assert isinstance(deck["slides"], list) and len(deck["slides"]) == 5


# ── orchestration: pending → done ────────────────────────────────────────


def test_run_live_generation_polls_until_done() -> None:
    client = FakeClient(
        post_response=FakeResponse(202, {"task_id": "tid-2"}),
        get_responses=[
            FakeResponse(409, {"detail": "Task is pending, slides not ready yet."}),
            FakeResponse(409, {"detail": "Task is running, slides not ready yet."}),
            FakeResponse(200, _DONE_DECK),
        ],
    )
    sleeps: list[float] = []
    deck = runner.run_live_generation(
        "p",
        base_url="http://x",
        theme="Editorial",
        search_web=False,
        slide_count=8,
        timeout_seconds=60,
        poll_interval_seconds=2.0,
        client=client,
        sleep=sleeps.append,
        now=lambda: 0.0,
    )
    assert len(client.gets) == 3
    assert sleeps == [2.0, 2.0]
    assert deck["slides"][0]["layout"] == "title"


# ── orchestration: failed task ───────────────────────────────────────────


def test_run_live_generation_raises_on_failed_task() -> None:
    client = FakeClient(
        post_response=FakeResponse(202, {"task_id": "tid-3"}),
        get_responses=[FakeResponse(409, {"detail": "Task is failed, slides not ready yet."})],
    )
    with pytest.raises(runner.LiveGenerationError):
        runner.run_live_generation(
            "p",
            base_url="http://x",
            theme="Editorial",
            search_web=False,
            slide_count=8,
            timeout_seconds=60,
            poll_interval_seconds=0,
            client=client,
            sleep=lambda s: None,
            now=lambda: 0.0,
        )


# ── orchestration: timeout ───────────────────────────────────────────────


def test_run_live_generation_raises_on_timeout() -> None:
    client = FakeClient(
        post_response=FakeResponse(202, {"task_id": "tid-4"}),
        get_responses=[FakeResponse(409, {"detail": "Task is pending"})] * 50,
    )
    times = iter([0.0, 5.0, 10.0, 15.0, 20.0, 25.0])
    with pytest.raises(runner.LiveGenerationTimeout):
        runner.run_live_generation(
            "p",
            base_url="http://x",
            theme="Editorial",
            search_web=False,
            slide_count=8,
            timeout_seconds=10.0,
            poll_interval_seconds=0,
            client=client,
            sleep=lambda s: None,
            now=lambda: next(times),
        )


# ── orchestration: post failure ──────────────────────────────────────────


def test_run_live_generation_raises_on_post_4xx() -> None:
    client = FakeClient(
        post_response=FakeResponse(503, {"detail": "queue down"}),
        get_responses=[],
    )
    with pytest.raises(runner.LiveGenerationError):
        runner.run_live_generation(
            "p",
            base_url="http://x",
            theme="Editorial",
            search_web=False,
            slide_count=8,
            timeout_seconds=10,
            poll_interval_seconds=0,
            client=client,
            sleep=lambda s: None,
            now=lambda: 0.0,
        )


def test_run_live_generation_raises_on_404() -> None:
    client = FakeClient(
        post_response=FakeResponse(202, {"task_id": "tid-5"}),
        get_responses=[FakeResponse(404, {"detail": "Task not found"})],
    )
    with pytest.raises(runner.LiveGenerationError):
        runner.run_live_generation(
            "p",
            base_url="http://x",
            theme="Editorial",
            search_web=False,
            slide_count=8,
            timeout_seconds=10,
            poll_interval_seconds=0,
            client=client,
            sleep=lambda s: None,
            now=lambda: 0.0,
        )


# ── main(): writes record, never makes real HTTP ─────────────────────────


def test_main_writes_record_with_fake_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("NEXUS_RUN_LIVE_EVAL", "true")
    monkeypatch.setenv("NEXUS_EVAL_OUTPUT_DIR", str(tmp_path))

    written: list[dict[str, Any]] = []

    def fake_writer(record: dict[str, Any]) -> Path:
        written.append(record)
        path = tmp_path / f"{record['prompt_id']}.json"
        path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def factory() -> FakeClient:
        return FakeClient(
            post_response=FakeResponse(202, {"task_id": "tid-7"}),
            get_responses=[FakeResponse(200, _DONE_DECK)],
        )

    rc = runner.main(
        argv=["--prompt-id", "biz-001", "--base-url", "http://fake.local"],
        client_factory=factory,
        write_record=fake_writer,
    )
    assert rc == 0
    assert len(written) == 1
    record = written[0]
    assert record["prompt_id"] == "biz-001"
    assert record["ran_live"] is True
    assert record["fixture_label"] is None
    assert isinstance(record["category_scores"]["deck_correctness"], int)
    # Confirm the file actually landed under the configured output dir.
    assert (tmp_path / "biz-001.json").is_file()


def test_main_returns_nonzero_when_generation_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("NEXUS_RUN_LIVE_EVAL", "true")
    monkeypatch.setenv("NEXUS_EVAL_OUTPUT_DIR", str(tmp_path))

    def factory() -> FakeClient:
        return FakeClient(
            post_response=FakeResponse(503, {"detail": "queue unavailable"}),
            get_responses=[],
        )

    rc = runner.main(
        argv=["--prompt-id", "biz-001", "--base-url", "http://fake.local"],
        client_factory=factory,
        write_record=lambda r: tmp_path / "x.json",
    )
    assert rc != 0


def test_main_does_not_import_httpx_when_using_injected_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Belt-and-braces: the default client (httpx) must not be touched
    when ``client_factory`` is provided. This is what guarantees offline
    tests cannot accidentally make real HTTP."""

    monkeypatch.setenv("NEXUS_RUN_LIVE_EVAL", "true")
    monkeypatch.setenv("NEXUS_EVAL_OUTPUT_DIR", str(tmp_path))

    def explode() -> None:
        raise AssertionError("default client must not be built when one is injected")

    monkeypatch.setattr(runner, "_build_default_client", explode)

    def factory() -> FakeClient:
        return FakeClient(
            post_response=FakeResponse(202, {"task_id": "tid-8"}),
            get_responses=[FakeResponse(200, _DONE_DECK)],
        )

    rc = runner.main(
        argv=["--prompt-id", "biz-001"],
        client_factory=factory,
        write_record=lambda r: tmp_path / "y.json",
    )
    assert rc == 0


# ── opt-in guard sanity: env stays clean across the rest of the suite ───


def test_env_flag_not_set_at_module_import_time() -> None:
    # If anyone in the test session leaked NEXUS_RUN_LIVE_EVAL=true, this
    # assertion will surface it. We do NOT want it set at module load.
    assert os.environ.get("NEXUS_RUN_LIVE_EVAL", "") in ("", "false", "False")
