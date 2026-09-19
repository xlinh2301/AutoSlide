# AutoSlide

> **Local-first agent for editing PowerPoint presentations with an Always-on Conversational Chatbot, deterministic OOXML mutation engine, and strict quality gates.**

---

## 🌟 Overview

AutoSlide transforms PowerPoint template editing by combining natural language conversation with a deterministic, template-preserving execution engine. With **ADS-002 (Always-on Agent Chat)**, AutoSlide provides an interactive conversational assistant that clarifies ambiguous requirements, produces typed plans, tracks web research provenance, requests explicit approval, and executes safe deck operations with full visual/structural verification.

---

## 🚀 Key Capabilities

- **Always-on Chatbot Rail**: Persistent multi-turn dialogue alongside the Before/After Canvas and Filmstrip.
- **Interactive Card System**:
  - `QuestionCard`: Targeted clarification questions with selectable options.
  - `PlanCard`: Typed edit plan with confidence score, target slides, operations, and explicit **Approve** / **Revise** actions.
  - `SourceCard`: Web research results with URLs, titles, retrieval timestamps, summaries, and **Approve** / **Reject** controls.
  - `ExecutionCard`: Real-time backend mutation and QA progress stepper.
  - `ReviewCard`: Visual & structural diff summary, PPTX download button, and follow-up prompt suggestions.
  - `ErrorCard`: Sanitized diagnostics with safe recovery and retry options.
- **Selection Context Binding**: Click slides on the filmstrip or drag selection boxes on the canvas to pass structured `SelectionContext` into chat turns.
- **Strict Two-Stage Approval Gates**: Zero automated edits and zero external content insertions occur without explicit user approval.
- **Zero Provider API Keys**: Integrates seamlessly with authenticated local agent CLI runtimes (`gemini`, `claude`, `openai`, `ollama`). No provider API keys are requested, stored, or logged by the application.
- **Safe Deck Operations**: Allowlisted operations for adding, deleting, duplicating, reordering slides, and inserting formatted content blocks.
- **Provenance & Attribution**: Web claims retain exact source metadata; generated content is explicitly labeled `AI_GENERATED`.
- **Immutable Source PPTX**: The original presentation is strictly immutable; all operations execute in isolated workspaces with full checkpoint recovery.

---

## 📐 System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        AutoSlide Studio UI                             │
│   ┌──────────────┐  ┌─────────────────────────┐  ┌─────────────────┐   │
│   │  Filmstrip   │  │   Canvas / Diff Viewer  │  │ Persistent Chat │   │
│   │ (Slide Nav)  │  │ (Before / After Render) │  │  (Action Cards) │   │
│   └──────┬───────┘  └────────────┬────────────┘  └────────┬────────┘   │
└──────────┼───────────────────────┼────────────────────────┼────────────┘
           │ Context Binding       │ Diff / Preview         │ Messages & Approvals
           ▼                       ▼                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend Service                          │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │                 Conversation Orchestration                     │   │
│   │  • Session Manager & Checkpoint Store                          │   │
│   │  • Clarification Engine (Targeted Questions)                   │   │
│   │  • Research & Provenance Service (Web & AI Generation)         │   │
│   │  • Approval Gate (Plan Decisions & Source Filtering)           │   │
│   └──────────────────────────────┬─────────────────────────────────┘   │
│                                  │ Approved Typed Plan                 │
│                                  ▼                                     │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │                   Deterministic Execution Pipeline             │   │
│   │  • Ingest & Inventory Parser                                   │   │
│   │  • OOXML Mutator (Text, Layout, Style, Deck Operations)        │   │
│   │  • LibreOffice Headless Renderer                               │   │
│   │  • Structural & Visual Quality Gates with Auto-Repair          │   │
│   └────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📡 API Endpoints

### Conversational Session Endpoints (`ADS-002`)
- `POST /api/v1/sessions`: Upload presentation PPTX and initialize a stateful conversational session.
- `POST /api/v1/sessions/{id}/messages`: Send user turns with optional `selection_context` (slide index, bounding box).
- `GET /api/v1/sessions/{id}`: Retrieve session state, brief, plan, sources, active job, and checkpoint path.
- `GET /api/v1/sessions/{id}/events`: Retrieve append-only redacted turn/event stream.
- `POST /api/v1/sessions/{id}/approve`: Submit approval decisions for plans (`kind: "plan"`) or sources (`kind: "sources"`).
- `POST /api/v1/sessions/{id}/execute`: Trigger execution for approved plans.

### Classic Job Endpoints (`ADS-001` Compatibility)
- `POST /api/v1/jobs`: Create asynchronous editing job.
- `GET /api/v1/jobs/{id}`: Poll job status, diff evidence, and artifact URLs.
- `GET /api/v1/jobs/{id}/download`: Download modified `.pptx` presentation.

---

## 🛠️ Quickstart

### Prerequisites
- Python 3.11+
- LibreOffice (for slide rendering and visual QA gates)
- Local agent CLI runtime (optional: `gemini`, `claude`, `openai`, `ollama`)

### Installation
```bash
# Clone the repository
git clone https://github.com/xlinh2301/AutoSlide.git
cd AutoSlide

# Install dependencies in editable mode
pip install -e ".[dev]"
```

### Starting the Server & Workbench
```bash
# Run the FastAPI server with UI static files
uvicorn autoslide.api:create_app --factory --host 0.0.0.0 --port 8000
```
Open your browser and navigate to: **`http://localhost:8000/ui`**

---

## 🧪 Verification & Testing

```bash
# 1. Compile syntax checks across all modules
python3 -m compileall src tests scripts

# 2. Run the complete automated test suite
pytest -v

# 3. Run UI static & DOM contract verification
PYTHONPATH=src:. python3 scripts/smoke_ui_check.py

# 4. Run End-to-End multi-turn conversation smoke flow
PYTHONPATH=src:. python3 scripts/smoke_conversation_flow.py
```

---

## 📚 Documentation & Specifications

- [Capability Map](CAPABILITY_MAP.md)
- [ADS-001: Foundation & Deterministic Editing Pipeline](.ai/specs/ADS-001/requirements.md)
- [ADS-002: Always-on Agent Chat & Provenance](.ai/specs/ADS-002/requirements.md)
- [ADS-002 Evidence Report](.ai/reports/ADS-002-evidence.md)
- [Implementation Plan](docs/superpowers/plans/2026-09-19-always-on-agent-chat.md)

---

## 📄 License

MIT License. See `LICENSE` for details.
