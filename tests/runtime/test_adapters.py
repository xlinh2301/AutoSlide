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


def test_codex_auth_argv_uses_login_status():
    adapter = CodexAdapter()
    assert adapter.auth_argv("/usr/bin/codex") == ["/usr/bin/codex", "login", "status"]


def test_codex_detection_probe(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/codex" if name == "codex" else None)

    def mock_run(argv, **kwargs):
        if "--version" in argv:
            return subprocess.CompletedProcess(argv, returncode=0, stdout="codex-cli 0.155.0\n", stderr="")
        if "login" in argv and "status" in argv:
            return subprocess.CompletedProcess(argv, returncode=0, stdout="Logged in using ChatGPT\n", stderr="")
        return subprocess.CompletedProcess(argv, returncode=1, stdout="", stderr="Error")

    adapter = CodexAdapter(run_cmd=mock_run)
    status = adapter.detect()
    assert status.installed is True
    assert status.authenticated is True
    assert status.available is True
    assert status.version == "codex-cli 0.155.0"
    assert status.executable == "/usr/bin/codex"


def test_antigravity_adapter_resolution_priority(monkeypatch, tmp_path: Path):
    from autoslide.runtime.adapters import AntigravityAdapter

    # Case 1: agy_c is present -> selects agy_c
    monkeypatch.setattr("shutil.which", lambda name: f"/bin/{name}" if name in ("agy_c", "agy", "antigravity") else None)
    adapter1 = AntigravityAdapter()
    assert adapter1.resolve_executable() == "/bin/agy_c"
    argv1 = adapter1.build_argv("Prompt 1", tmp_path)
    assert argv1 == ["/bin/agy_c", "--print", "Prompt 1", "--add-dir", str(tmp_path)]
    assert adapter1.auth_argv("/bin/agy_c") == ["/bin/agy_c", "models"]

    # Case 2: only agy is present -> selects agy
    monkeypatch.setattr("shutil.which", lambda name: f"/bin/{name}" if name in ("agy", "antigravity") else None)
    adapter2 = AntigravityAdapter()
    assert adapter2.resolve_executable() == "/bin/agy"
    argv2 = adapter2.build_argv("Prompt 2", tmp_path)
    assert argv2 == ["/bin/agy", "--print", "Prompt 2", "--add-dir", str(tmp_path)]

    # Case 3: only antigravity is present -> selects antigravity
    monkeypatch.setattr("shutil.which", lambda name: f"/bin/{name}" if name == "antigravity" else None)
    adapter3 = AntigravityAdapter()
    assert adapter3.resolve_executable() == "/bin/antigravity"

    # Case 4: none present -> None
    monkeypatch.setattr("shutil.which", lambda name: None)
    adapter4 = AntigravityAdapter()
    assert adapter4.resolve_executable() is None
    status4 = adapter4.detect()
    assert status4.installed is False
    assert status4.authenticated is False
    assert status4.available is False


def test_antigravity_detection_success(monkeypatch):
    from autoslide.runtime.adapters import AntigravityAdapter

    monkeypatch.setattr("shutil.which", lambda name: "/home/user/.local/bin/agy_c" if name == "agy_c" else None)

    def mock_run(argv, **kwargs):
        if "--version" in argv:
            return subprocess.CompletedProcess(argv, returncode=0, stdout="1.2.6\n", stderr="")
        if "models" in argv:
            return subprocess.CompletedProcess(argv, returncode=0, stdout="gemini-3.8-flash-high\n", stderr="")
        return subprocess.CompletedProcess(argv, returncode=1, stdout="", stderr="Fail")

    adapter = AntigravityAdapter(run_cmd=mock_run)
    status = adapter.detect()
    assert status.installed is True
    assert status.authenticated is True
    assert status.available is True
    assert status.version == "1.2.6"
    assert status.executable == "/home/user/.local/bin/agy_c"

