# AutoSlide Foundation Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the local job runtime that isolates workspaces, tracks job state, detects authenticated agent CLIs, streams redacted events, and supports cancellation/recovery for the AutoSlide MVP.

**Architecture:** A Python FastAPI service owns a SQLite job registry and one filesystem workspace per job. A runtime adapter registry detects Codex, Gemini CLI and Claude Code without storing provider secrets. Every job transition writes an append-only redacted event and a checkpoint manifest; later PPTX phases consume these contracts without depending on a specific agent provider.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, SQLite, pytest, httpx, `subprocess`, pathlib, JSON Schema-compatible Pydantic models.

**Spec:** `CAPABILITY_MAP.md`, `.ai/specs/ADS-001/requirements.md`, `.ai/specs/ADS-001/design.md`

## Global Constraints

- MVP input is `.pptx` plus natural-language instruction; DOCX/XLSX/PDF/image reference ingestion is deferred to phase 7.
- The original input file is never modified in place.
- The application never requests, stores or logs provider API keys, cookies or tokens.
- Agent execution is limited to an isolated job workspace and an allowlisted CLI runtime.
- Every accepted job must have checkpoints, redacted events and a verification-ready artifact manifest.
- Unknown operations, unsafe paths, ambiguous targets and unsupported runtime states fail closed.
- Use strict Conventional Commits without AI attribution.
- Tests run with `pytest -q`; syntax checks run with `python3 -m compileall src tests`.

---

### Task 1: Create the Python project skeleton and test harness

**Files:**
- Create: `pyproject.toml`
- Create: `src/autoslide/__init__.py`
- Create: `src/autoslide/config.py`
- Create: `tests/test_config.py`
- Create: `.gitignore`

**Interfaces:**
- `autoslide.config.Settings.from_env() -> Settings`
- `Settings.data_root: pathlib.Path`
- `Settings.max_job_size_bytes: int`
- `Settings.job_timeout_seconds: int`
- `Settings.allowed_runtimes: tuple[str, ...]`

- [ ] **Step 1: Write the failing configuration tests**

```python
from pathlib import Path

from autoslide.config import Settings


def test_defaults_are_local_and_api_key_free(tmp_path: Path):
    settings = Settings.from_env({"AUTOSLIDE_DATA_ROOT": str(tmp_path)})
    assert settings.data_root == tmp_path
    assert settings.allowed_runtimes == ("codex", "gemini", "claude")
    assert not hasattr(settings, "provider_api_key")


def test_paths_are_created_by_explicit_bootstrap(tmp_path: Path):
    settings = Settings.from_env({"AUTOSLIDE_DATA_ROOT": str(tmp_path / "data")})
    settings.ensure_directories()
    assert (tmp_path / "data" / "jobs").is_dir()
    assert (tmp_path / "data" / "artifacts").is_dir()
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `pytest -q tests/test_config.py`

Expected: FAIL because the package and `Settings` contract do not exist.

- [ ] **Step 3: Add the minimal package and configuration implementation**

Implement `Settings` as a frozen Pydantic model or dataclass. Read only these environment variables: `AUTOSLIDE_DATA_ROOT`, `AUTOSLIDE_MAX_JOB_SIZE_BYTES`, `AUTOSLIDE_JOB_TIMEOUT_SECONDS` and `AUTOSLIDE_ALLOWED_RUNTIMES`. Reject relative `AUTOSLIDE_DATA_ROOT` values and reject a runtime name outside `codex`, `gemini`, `claude`.

- [ ] **Step 4: Run focused tests and syntax checks**

Run: `pytest -q tests/test_config.py && python3 -m compileall src tests`

Expected: PASS with two tests passing and no syntax errors.

- [ ] **Step 5: Commit the skeleton**

```bash
git add pyproject.toml src/autoslide tests/test_config.py .gitignore
git commit -m "feat: add AutoSlide foundation configuration"
```

### Task 2: Implement job workspace and checkpoint registry

**Files:**
- Create: `src/autoslide/jobs/models.py`
- Create: `src/autoslide/jobs/workspace.py`
- Create: `src/autoslide/jobs/registry.py`
- Create: `tests/jobs/test_workspace.py`
- Create: `tests/jobs/test_registry.py`

**Interfaces:**
- `JobState`: `CREATED`, `INGESTING`, `PLANNING`, `EXECUTING`, `RENDERING`, `VERIFYING`, `REPAIRING`, `AWAITING_USER_APPROVAL`, `ACCEPTED`, `FAILED`, `CANCELLED`
- `JobRecord(job_id, state, instruction, input_sha256, created_at, updated_at)`
- `JobWorkspace.create(root: Path, job_id: str) -> JobWorkspace`
- `JobWorkspace.path_for(name: str) -> Path`
- `JobWorkspace.write_checkpoint(stage: str, source: Path) -> CheckpointRecord`
- `JobRegistry.create(instruction: str, input_sha256: str) -> JobRecord`
- `JobRegistry.transition(job_id: str, new_state: JobState) -> JobRecord`
- `JobRegistry.get(job_id: str) -> JobRecord`

- [ ] **Step 1: Write tests for workspace isolation and checkpoint hashing**

```python
def test_workspace_contains_only_job_scoped_paths(tmp_path):
    workspace = JobWorkspace.create(tmp_path, "job_123")
    assert workspace.root == tmp_path / "jobs" / "job_123"
    assert workspace.path_for("input.pptx").parent == workspace.root
    assert workspace.path_for("../outside.txt").parent == workspace.root


def test_checkpoint_records_sha256(tmp_path):
    source = tmp_path / "working.pptx"
    source.write_bytes(b"pptx-fixture")
    workspace = JobWorkspace.create(tmp_path, "job_123")
    checkpoint = workspace.write_checkpoint("INGESTED", source)
    assert checkpoint.stage == "INGESTED"
    assert len(checkpoint.sha256) == 64
    assert checkpoint.path.exists()
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest -q tests/jobs/test_workspace.py tests/jobs/test_registry.py`

Expected: FAIL because workspace and registry contracts are absent.

- [ ] **Step 3: Implement safe workspace and SQLite registry**

Use `pathlib.Path.resolve()` to prevent traversal, create `input`, `working`, `checkpoints`, `previews`, `artifacts` and `logs` directories, copy source files into the workspace, compute SHA-256, and reject symlinked destinations. Use SQLite transactions for job creation and state transitions. Reject transitions not allowed by the state machine.

- [ ] **Step 4: Add recovery and cancellation tests**

Cover: duplicate job IDs, invalid transition, missing job, checkpoint parent linkage, cancellation from active states and idempotent cancellation.

- [ ] **Step 5: Run tests and commit**

Run: `pytest -q tests/jobs && python3 -m compileall src tests`

```bash
git add src/autoslide/jobs tests/jobs
git commit -m "feat: add isolated job workspace registry"
```

### Task 3: Implement redacted event logging and runtime status models

**Files:**
- Create: `src/autoslide/events.py`
- Create: `src/autoslide/runtime/models.py`
- Create: `tests/test_events.py`
- Create: `tests/runtime/test_models.py`

**Interfaces:**
- `Redactor.redact(value: str) -> str`
- `EventLog.append(job_id: str, event_type: str, payload: dict) -> EventRecord`
- `RuntimeStatus(name, installed, version, authenticated, executable, reason)`
- `AgentEvent(job_id, sequence, kind, message, timestamp, metadata)`

- [ ] **Step 1: Write redaction tests**

```python
def test_redactor_removes_secret_like_values():
    text = "Authorization: Bearer abc123 and OPENAI_API_KEY=secret-value"
    safe = Redactor.redact(text)
    assert "abc123" not in safe
    assert "secret-value" not in safe
    assert "[REDACTED]" in safe
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest -q tests/test_events.py tests/runtime/test_models.py`

Expected: FAIL because the event and model interfaces do not exist.

- [ ] **Step 3: Implement deterministic redaction and append-only events**

Redact bearer tokens, common API-key environment assignments, cookie names/values, private-key blocks and absolute credential paths. Persist only redacted JSON. Add monotonically increasing per-job sequence numbers.

- [ ] **Step 4: Add event ordering and serialization tests**

Verify sequence ordering, JSON serialization, timestamp presence, stable event kinds and that runtime status never contains credential contents.

- [ ] **Step 5: Run tests and commit**

Run: `pytest -q tests/test_events.py tests/runtime/test_models.py`

```bash
git add src/autoslide/events.py src/autoslide/runtime/models.py tests/test_events.py tests/runtime/test_models.py
git commit -m "feat: add redacted job event contracts"
```

### Task 4: Implement CLI runtime detection and adapter contract

**Files:**
- Create: `src/autoslide/runtime/base.py`
- Create: `src/autoslide/runtime/discovery.py`
- Create: `src/autoslide/runtime/adapters.py`
- Create: `tests/runtime/test_discovery.py`
- Create: `tests/runtime/test_adapters.py`

**Interfaces:**
- `RuntimeAdapter.detect() -> RuntimeStatus`
- `RuntimeAdapter.start(job_id: str, prompt: str, workspace: Path) -> RuntimeHandle`
- `RuntimeAdapter.cancel(handle: RuntimeHandle) -> None`
- `RuntimeRegistry.detect_all() -> list[RuntimeStatus]`
- `RuntimeRegistry.get(name: str) -> RuntimeAdapter`

- [ ] **Step 1: Write discovery tests with mocked executables**

```python
def test_discovery_reports_missing_runtime(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    status = CodexAdapter().detect()
    assert status.installed is False
    assert status.authenticated is False


def test_discovery_does_not_read_api_key_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-read")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/codex")
    status = CodexAdapter().detect()
    assert "must-not-be-read" not in repr(status)
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest -q tests/runtime/test_discovery.py tests/runtime/test_adapters.py`

Expected: FAIL because adapter classes do not exist.

- [ ] **Step 3: Implement provider-neutral adapter base and mocked process runner**

Discover executable with `shutil.which`, retrieve version using a fixed argument list, and determine authentication only through a safe runtime-specific status command or configured login signal. Never inspect or print cookie/API-key files. For execution, pass prompt and workspace through argument-safe subprocess APIs; disable shell interpretation and capture stdout/stderr through the redactor.

- [ ] **Step 4: Add timeout, cancellation and exit-code tests**

Use a fake process runner to verify bounded timeout, cancellation, non-zero exit conversion to an error event and successful final event. Do not invoke real provider CLIs in unit tests.

- [ ] **Step 5: Run tests and commit**

Run: `pytest -q tests/runtime && python3 -m compileall src tests`

```bash
git add src/autoslide/runtime tests/runtime
git commit -m "feat: add local agent runtime adapters"
```

### Task 5: Implement foundation API and integration tests

**Files:**
- Create: `src/autoslide/api.py`
- Create: `src/autoslide/main.py`
- Create: `tests/api/test_jobs.py`
- Create: `tests/integration/test_foundation_flow.py`

**Interfaces:**
- `POST /api/v1/jobs` with multipart `template` and form `instruction`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/events`
- `POST /api/v1/jobs/{job_id}/cancel`
- `GET /api/v1/runtimes`

- [ ] **Step 1: Write API contract tests**

```python
def test_create_job_returns_202_and_isolated_status(client, valid_pptx):
    response = client.post(
        "/api/v1/jobs",
        files={"template": ("template.pptx", valid_pptx, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        data={"instruction": "Change the title on slide 1"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["state"] == "CREATED"
    assert body["job_id"]


def test_invalid_extension_is_rejected(client):
    response = client.post(
        "/api/v1/jobs",
        files={"template": ("input.txt", b"not pptx", "text/plain")},
        data={"instruction": "Edit it"},
    )
    assert response.status_code == 400
```

- [ ] **Step 2: Run API tests and verify failure**

Run: `pytest -q tests/api/test_jobs.py tests/integration/test_foundation_flow.py`

Expected: FAIL because the FastAPI application and routes do not exist.

- [ ] **Step 3: Implement API dependency wiring**

Create the FastAPI app factory with injected `Settings`, `JobRegistry`, `JobWorkspace` and `RuntimeRegistry`. Validate extension, content size, instruction length and job path. Return only job identifiers and safe metadata; never return environment values or raw subprocess output.

- [ ] **Step 4: Add integration flow tests**

Use a fake runtime adapter and a minimal valid PPTX fixture to verify: create job, status retrieval, event stream ordering, cancellation, invalid input, oversized input and runtime listing.

- [ ] **Step 5: Run the foundation verification suite**

Run: `pytest -q && python3 -m compileall src tests`

Expected: all foundation tests pass and compilation succeeds.

- [ ] **Step 6: Commit the foundation vertical slice**

```bash
git add src/autoslide/api.py src/autoslide/main.py tests/api tests/integration
git commit -m "feat: add AutoSlide foundation job API"
```

## Verification checklist

- [ ] `pytest -q` passes.
- [ ] `python3 -m compileall src tests` passes.
- [ ] No test or log contains provider credentials, cookies or API-key values.
- [ ] Job workspace traversal tests pass.
- [ ] Runtime adapters use argument arrays, not shell interpolation.
- [ ] Invalid state transitions are rejected.
- [ ] API contract returns the documented status categories.
- [ ] The implementation remains limited to foundation-runtime; PPTX editing starts only in the next plan.
