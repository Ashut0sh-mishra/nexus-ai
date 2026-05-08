"""Docker-based code execution sandbox (CodeAct).

Executes untrusted Python code inside a disposable, network-disabled,
read-only container that matches the Manus sandbox image
(Ubuntu 22.04 + Python 3.10.12 + Node 20.18.0).
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import tarfile
import tempfile
import textwrap
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional

logger = logging.getLogger("nexus.sandbox.executor")

DEFAULT_IMAGE = "nexus-sandbox:latest"


@dataclass
class ExecutionResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float


class SandboxExecutor:
    """Run a snippet of Python in a fresh container. One container per call."""

    def __init__(self, image: str = DEFAULT_IMAGE) -> None:
        self.image = image
        self._client = None

    def _docker(self):
        if self._client is None:
            try:
                import docker  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "docker SDK is not installed. Run: pip install docker"
                ) from exc
            self._client = docker.from_env()
        return self._client

    async def run_python(
        self,
        code: str,
        timeout_s: int = 30,
        mem_limit: str = "512m",
        cpu_quota: int = 50_000,
    ) -> ExecutionResult:
        return await asyncio.to_thread(
            self._run_python_sync, code, timeout_s, mem_limit, cpu_quota
        )

    def _run_python_sync(
        self, code: str, timeout_s: int, mem_limit: str, cpu_quota: int
    ) -> ExecutionResult:
        import time

        client = self._docker()
        prepared = textwrap.dedent(code)

        # Write code to an in-memory tar so we can copy it into the container.
        tarball = self._make_tarball("script.py", prepared.encode("utf-8"))

        container = client.containers.create(
            image=self.image,
            command=["python", "/work/script.py"],
            working_dir="/work",
            network_disabled=True,
            mem_limit=mem_limit,
            nano_cpus=cpu_quota * 10_000,  # cpu_quota * 100_000ns / 100_000us = quota * 10_000ns
            read_only=False,
            tty=False,
            stdin_open=False,
            detach=True,
        )

        start = time.monotonic()
        try:
            container.put_archive("/work", tarball)
            container.start()
            try:
                exit_status = container.wait(timeout=timeout_s)
                exit_code = int(exit_status.get("StatusCode", 1))
            except Exception:
                container.kill()
                return ExecutionResult(
                    ok=False,
                    exit_code=124,
                    stdout="",
                    stderr=f"Sandbox timed out after {timeout_s}s",
                    duration_s=time.monotonic() - start,
                )
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
            return ExecutionResult(
                ok=exit_code == 0,
                exit_code=exit_code,
                stdout=stdout[-100_000:],
                stderr=stderr[-100_000:],
                duration_s=time.monotonic() - start,
            )
        finally:
            try:
                container.remove(force=True)
            except Exception:  # pragma: no cover
                pass

    @staticmethod
    def _make_tarball(name: str, data: bytes) -> bytes:
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = 0o644
            tar.addfile(info, BytesIO(data))
        return buf.getvalue()
