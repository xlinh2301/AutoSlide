# Capability Map: Always-on Agent Chat for AutoSlide

| Module id | Responsibility | Depends on |
|---|---|---|
| conversation-session | Persistent agent chat, turn history, session state | ADS-001 job workspace |
| clarification-planner | Ask targeted questions and produce a typed edit brief/plan | conversation-session, PPTX inventory |
| content-research | Search web or generate content through the selected agent CLI; preserve provenance | conversation-session, clarification-planner |
| deck-operations | Add, delete, duplicate, reorder slides and add/edit content | clarification-planner, PPTX executor |
| approval-review | Approve/revise plan, sources and execution result | conversation-session, content-research, preview-diff |
| provenance | Record source URLs, timestamps, generated-content labels and content-to-slide links | content-research, deck-operations |
| conversational-ui | Always-visible chatbot with plan/source/action cards beside canvas preview | conversation-session, approval-review |

Build order: conversation-session → clarification-planner → deck-operations → content-research → approval-review/provenance → conversational-ui integration.

The existing ADS-001 PPTX-only upload, execution, rendering, QA and download contracts remain the foundation. Reference-file ingestion remains deferred unless separately approved.
