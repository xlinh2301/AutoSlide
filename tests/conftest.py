import io
from pathlib import Path
import zipfile
from fastapi.testclient import TestClient
import pytest

from autoslide.api import create_app
from autoslide.config import Settings
from autoslide.events import EventLog
from autoslide.jobs.registry import JobRegistry
from autoslide.runtime.adapters import FakeRuntimeAdapter
from autoslide.runtime.discovery import RuntimeRegistry


from tests.fixtures.pptx_samples import create_minimal_pptx


@pytest.fixture
def valid_pptx() -> bytes:
    """Create a minimal valid zip/pptx byte stream for testing."""
    return create_minimal_pptx()


@pytest.fixture
def test_env(tmp_path: Path):
    data_root = tmp_path / "autoslide_data"
    settings = Settings.from_env({
        "AUTOSLIDE_DATA_ROOT": str(data_root),
        "AUTOSLIDE_MAX_JOB_SIZE_BYTES": "1048576",  # 1MB for test
        "AUTOSLIDE_JOB_TIMEOUT_SECONDS": "60",
    })
    settings.ensure_directories()
    registry = JobRegistry(data_root / "jobs.db")
    event_log = EventLog(log_path=data_root / "logs")
    runtime_registry = RuntimeRegistry([
        FakeRuntimeAdapter(mock_stdout="Done", mock_exit_code=0)
    ])
    app = create_app(
        settings=settings,
        registry=registry,
        runtime_registry=runtime_registry,
        event_log=event_log,
    )
    return {
        "app": app,
        "settings": settings,
        "registry": registry,
        "event_log": event_log,
        "runtime_registry": runtime_registry,
    }


@pytest.fixture
def client(test_env):
    return TestClient(test_env["app"])
