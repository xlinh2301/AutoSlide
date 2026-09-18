"""Concrete CLI runtime adapters for Codex, Gemini, and Claude."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable

from autoslide.events import EventLog, EventRecord, Redactor
from autoslide.runtime.base import RuntimeAdapter, RuntimeHandle
from autoslide.runtime.models import RuntimeStatus


class BaseRuntimeAdapter(RuntimeAdapter):
    """Base runtime adapter with safe process execution, redaction, and bounded timeouts."""

    def __init__(
        self,
        process_runner: Callable[..., Any] | None = None,
        run_cmd: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ):
        self.process_runner = process_runner or subprocess.Popen
        self.run_cmd = run_cmd or subprocess.run

    def build_argv(self, prompt: str, workspace: Path) -> list[str]:
        """Build safe argument array for CLI execution."""
        executable = shutil.which(self.executable_name) or self.executable_name
        return [executable, "run", "--prompt", prompt]

    def auth_argv(self, executable: str) -> list[str]:
        """Return safe command array to verify authentication status."""
        return [executable, "auth", "status"]

    def detect(self) -> RuntimeStatus:
        """Probe the system for binary presence, version, and authentication state."""
        which_path = shutil.which(self.executable_name)
        if not which_path:
            return RuntimeStatus(
                name=self.name,
                installed=False,
                version=None,
                authenticated=False,
                executable=None,
                reason=f"Executable '{self.executable_name}' not found in PATH",
            )

        version: str | None = None
        try:
            res = self.run_cmd(
                [which_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                version = res.stdout.strip()
        except Exception:
            version = None

        authenticated = False
        reason: str | None = None
        try:
            auth_res = self.run_cmd(
                self.auth_argv(which_path),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if auth_res.returncode == 0:
                authenticated = True
            else:
                reason = auth_res.stderr.strip() or "Not authenticated"
        except Exception:
            authenticated = False
            reason = "Authentication check failed"

        return RuntimeStatus(
            name=self.name,
            installed=True,
            version=version,
            authenticated=authenticated,
            executable=which_path,
            reason=reason,
        )

    def start(
        self,
        job_id: str,
        prompt: str,
        workspace: Path,
        timeout_seconds: int = 300,
    ) -> RuntimeHandle:
        """Spawn the agent process safely without a shell."""
        argv = self.build_argv(prompt, workspace)
        now = datetime.now(timezone.utc).isoformat()

        proc = self.process_runner(
            argv,
            cwd=workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
        )

        return RuntimeHandle(
            job_id=job_id,
            adapter_name=self.name,
            process=proc,
            started_at=now,
            timeout_seconds=timeout_seconds,
            argv=argv,
        )

    def cancel(self, handle: RuntimeHandle) -> None:
        """Terminate a running process cleanly."""
        proc = handle.process
        if proc is not None:
            if hasattr(proc, "terminate"):
                proc.terminate()
            elif hasattr(proc, "kill"):
                proc.kill()

    def wait_process(self, handle: RuntimeHandle, timeout: float | None = None) -> int:
        """Wait for process completion, terminating if the timeout threshold is exceeded."""
        effective_timeout = timeout if timeout is not None else handle.timeout_seconds
        proc = handle.process
        try:
            if hasattr(proc, "communicate"):
                _, _ = proc.communicate(timeout=effective_timeout)
                return getattr(proc, "returncode", 0)
            elif hasattr(proc, "wait"):
                return proc.wait(timeout=effective_timeout)
            return 0
        except (subprocess.TimeoutExpired, TimeoutError) as exc:
            self.cancel(handle)
            raise TimeoutError(
                f"Process for job {handle.job_id} timed out after {effective_timeout}s"
            ) from exc

    def collect_and_stream(
        self,
        handle: RuntimeHandle,
        event_log: EventLog | None = None,
    ) -> tuple[int, list[EventRecord]]:
        """Collect process output, redact all strings, and append telemetry events."""
        proc = handle.process
        stdout_raw, stderr_raw = "", ""

        if hasattr(proc, "communicate"):
            out, err = proc.communicate()
            stdout_raw = out or ""
            stderr_raw = err or ""
        elif hasattr(proc, "stdout") and hasattr(proc, "stderr"):
            stdout_raw = proc.stdout.read() if proc.stdout else ""
            stderr_raw = proc.stderr.read() if proc.stderr else ""

        stdout_safe = Redactor.redact(stdout_raw)
        stderr_safe = Redactor.redact(stderr_raw)
        exit_code = getattr(proc, "returncode", 0)

        events: list[EventRecord] = []
        if event_log is not None:
            if stdout_safe:
                e_out = event_log.append(
                    handle.job_id,
                    "RUNTIME_OUTPUT",
                    {"stream": "stdout", "message": stdout_safe},
                )
                events.append(e_out)
            if exit_code != 0:
                e_err = event_log.append(
                    handle.job_id,
                    "RUNTIME_ERROR",
                    {
                        "exit_code": exit_code,
                        "message": stderr_safe or f"Process exited with code {exit_code}",
                    },
                )
                events.append(e_err)
            else:
                e_fin = event_log.append(
                    handle.job_id,
                    "RUNTIME_COMPLETED",
                    {"exit_code": 0, "message": "Runtime completed successfully"},
                )
                events.append(e_fin)

        return exit_code, events


class CodexAdapter(BaseRuntimeAdapter):
    """Runtime adapter for OpenAI Codex CLI."""

    name = "codex"
    executable_name = "codex"

    def build_argv(self, prompt: str, workspace: Path) -> list[str]:
        executable = shutil.which(self.executable_name) or self.executable_name
        return [executable, "exec", "--prompt", prompt, "--workspace", str(workspace)]

    def auth_argv(self, executable: str) -> list[str]:
        return [executable, "auth", "status"]


class GeminiAdapter(BaseRuntimeAdapter):
    """Runtime adapter for Gemini CLI (agy)."""

    name = "gemini"
    executable_name = "gemini"

    def build_argv(self, prompt: str, workspace: Path) -> list[str]:
        executable = shutil.which(self.executable_name) or self.executable_name
        return [executable, "run", "--prompt", prompt, "--dir", str(workspace)]

    def auth_argv(self, executable: str) -> list[str]:
        return [executable, "auth", "check"]


class ClaudeAdapter(BaseRuntimeAdapter):
    """Runtime adapter for Claude Code CLI."""

    name = "claude"
    executable_name = "claude"

    def build_argv(self, prompt: str, workspace: Path) -> list[str]:
        executable = shutil.which(self.executable_name) or self.executable_name
        return [executable, "--prompt", prompt, "--cwd", str(workspace)]

    def auth_argv(self, executable: str) -> list[str]:
        return [executable, "auth", "status"]


class FakeRuntimeAdapter(BaseRuntimeAdapter):
    """Mock adapter for deterministic testing of timeouts, errors, and cancellation."""

    name = "fake"
    executable_name = "fake"

    def __init__(
        self,
        mock_stdout: str = "",
        mock_stderr: str = "",
        mock_exit_code: int = 0,
        custom_process: Any | None = None,
    ):
        super().__init__()
        self.mock_stdout = mock_stdout
        self.mock_stderr = mock_stderr
        self.mock_exit_code = mock_exit_code
        self.custom_process = custom_process

    def start(
        self,
        job_id: str,
        prompt: str,
        workspace: Path,
        timeout_seconds: int = 300,
    ) -> RuntimeHandle:
        if self.custom_process is not None:
            proc = self.custom_process
        else:
            class MockProc:
                pid = 1111

                def __init__(self, out: str, err: str, code: int):
                    self._out = out
                    self._err = err
                    self.returncode = code
                    self.terminated = False

                def poll(self):
                    return self.returncode

                def communicate(self, timeout=None):
                    return (self._out, self._err)

                def terminate(self):
                    self.terminated = True
                    self.returncode = -15

                def kill(self):
                    self.terminated = True
                    self.returncode = -9

            proc = MockProc(self.mock_stdout, self.mock_stderr, self.mock_exit_code)

        now = datetime.now(timezone.utc).isoformat()
        return RuntimeHandle(
            job_id=job_id,
            adapter_name=self.name,
            process=proc,
            started_at=now,
            timeout_seconds=timeout_seconds,
            argv=["fake", "--prompt", prompt],
        )
