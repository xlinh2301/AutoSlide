# Capability Map: Always-on Agent Chat for AutoSlide

| Module ID | Responsibility | Depends on | Status |
|---|---|---|---|
| `conversation-session` | Persistent agent chat, turn history, session state & checkpoints | ADS-001 job workspace | ✅ COMPLETED |
| `clarification-planner` | Ask targeted questions and produce a typed edit brief/plan | `conversation-session`, PPTX inventory | ✅ COMPLETED |
| `session-api` | FastAPI endpoints for session lifecycle, messaging, approvals, and execution | `conversation-session`, `clarification-planner` | ✅ COMPLETED |
| `content-research` | Search web or generate content through selected agent CLI; preserve provenance | `conversation-session`, `clarification-planner` | ✅ COMPLETED |
| `deck-operations` | Add, delete, duplicate, reorder slides and add/edit content | `clarification-planner`, PPTX executor | ✅ COMPLETED |
| `approval-review` | Approve/revise plan, sources and execution result | `conversation-session`, `content-research`, `preview-diff` | ✅ COMPLETED |
| `provenance` | Record source URLs, timestamps, generated-content labels and content-to-slide links | `content-research`, `deck-operations` | ✅ COMPLETED |
| `conversational-ui` | Always-visible chatbot with plan/source/action cards beside canvas preview | `conversation-session`, `approval-review` | ✅ COMPLETED |

## Delivered Build Order

`conversation-session → clarification-planner → session-api → content-research/provenance → deck-operations → conversational-ui integration`

The existing ADS-001 PPTX-only upload, execution, rendering, QA and download contracts remain the foundation. Reference-file ingestion remains deferred to future iterations.
