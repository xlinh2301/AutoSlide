from pathlib import Path
import subprocess
import pytest

from autoslide.events import EventLog
from autoslide.runtime.adapters import CodexAdapter, FakeRuntimeAdapter
from autoslide.runtime.base import RuntimeHandle


def test_adapter_start_uses_argv_and_no_shell(tmp_path: Path):
    captured_calls = []

    def fake_popen(argv, **kwargs):
        captured_calls.append({"argv": argv, "kwargs": kwargs})

        class FakeProcess:
            pid = 1234
            returncode = 0

            def poll(self):
                return 0

            def communicate(self, timeout=None):
                return ("Output", "")

            def terminate(self):
                pass

        return FakeProcess()

    adapter = CodexAdapter(process_runner=fake_popen)
    handle = adapter.start("job_1", "Edit slide 1", tmp_path)

    assert isinstance(handle, RuntimeHandle)
    assert handle.job_id == "job_1"
    assert handle.adapter_name == "codex"
    assert len(captured_calls) == 1
    call = captured_calls[0]

    # Verify argument array is passed without shell interpretation
    assert isinstance(call["argv"], list)
    assert "codex" in call["argv"][0]
    assert call["kwargs"].get("shell") is False
    assert call["kwargs"].get("cwd") == tmp_path


def test_adapter_redacts_stdout_and_stderr(tmp_path: Path):
    event_log = EventLog()
    adapter = FakeRuntimeAdapter(
        mock_stdout="Done with OPENAI_API_KEY=super-secret-key",
        mock_stderr="Warning with Bearer secret-token-xyz",
        mock_exit_code=0,
    )

    handle = adapter.start("job_2", "Prompt", tmp_path)
    exit_code, events = adapter.collect_and_stream(handle, event_log=event_log)

    assert exit_code == 0
    all_messages = " ".join([e.payload.get("message", "") for e in events])
    assert "super-secret-key" not in all_messages
    assert "secret-token-xyz" not in all_messages
    assert "[REDACTED]" in all_messages


def test_adapter_enforces_timeout(tmp_path: Path):
    class HangingProcess:
        pid = 5678
        returncode = None
        terminated = False

        def poll(self):
            return None

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd=["test"], timeout=timeout)

        def terminate(self):
            self.terminated = True
            self.returncode = -15

        def kill(self):
            self.terminated = True
            self.returncode = -9

    adapter = FakeRuntimeAdapter(custom_process=HangingProcess())
    handle = adapter.start("job_3", "Long running prompt", tmp_path, timeout_seconds=1)

    with pytest.raises(TimeoutError, match="timed out"):
        adapter.wait_process(handle, timeout=0.1)

    assert handle.process.terminated is True


def test_adapter_cancel_terminates_process(tmp_path: Path):
    class RunningProcess:
        pid = 9999
        terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.terminated = True

    proc = RunningProcess()
    adapter = FakeRuntimeAdapter(custom_process=proc)
    handle = adapter.start("job_4", "Cancel test", tmp_path)

    adapter.cancel(handle)
    assert proc.terminated is True


def test_adapter_nonzero_exit_emits_error_event(tmp_path: Path):
    event_log = EventLog()
    adapter = FakeRuntimeAdapter(
        mock_stdout="",
        mock_stderr="Fatal syntax error in prompt script",
        mock_exit_code=1,
    )

    handle = adapter.start("job_5", "Bad prompt", tmp_path)
    exit_code, events = adapter.collect_and_stream(handle, event_log=event_log)

    assert exit_code == 1
    event_types = [e.event_type for e in events]
    assert "RUNTIME_ERROR" in event_types
    err_event = next(e for e in events if e.event_type == "RUNTIME_ERROR")
    assert "Fatal syntax error" in err_event.payload.get("message", "")
