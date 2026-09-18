# Requirements: AutoSlide MVP and Roadmap

**Spec ID:** ADS-001  
**Status:** DRAFT — Gate #0 pending  
**Scope:** PPTX template + natural-language update; reference documents deferred

## 1. Objective

Build a local-first application that accepts an existing `.pptx` template or sample deck and a natural-language instruction, performs a bounded edit on the deck, verifies that the requested change happened without unintended changes, and returns an editable `.pptx`.

The MVP must work without an application-managed provider API key. It may invoke locally installed and authenticated CLI runtimes such as Codex, Gemini CLI or Claude Code.

## 2. Users and user stories

### US-01 — Edit an existing template

As a user, I upload a PPTX template and describe an edit so that I receive an updated PPTX that retains the original design.

### US-02 — Update selected slide content

As a user, I can say “change the title on slide 3 to …” or “replace the highlighted KPI text” and the system targets only the requested object.

### US-03 — Review before download

As a user, I can inspect before/after previews, changed objects, warnings and QA results before accepting the output.

### US-04 — Safe refusal

As a user, I receive a clarification or review request when the instruction is ambiguous, unsupported, impossible to verify or likely to cause layout damage.

## 3. In scope for MVP

- PPTX upload and validation.
- Natural-language instruction input.
- Slide/object inventory and thumbnails.
- Text replacement, text formatting, image replacement, shape movement/resizing, slide duplication and deletion where supported.
- Explicit target slide and object references.
- Typed edit plan with preservation scope.
- Deterministic execution through approved tools.
- Structural before/after diff.
- Local rendering to preview images/PDF.
- Overflow, clipping, missing-target and file-integrity checks.
- Job status, logs, preview and final download.
- Runtime detection for Codex, Gemini CLI and Claude Code.
- No storage or collection of provider API keys.

## 4. Deferred scope

- DOCX, XLSX, PDF and image reference ingestion.
- Data provenance from cells/paragraphs.
- Automatic chart data refresh from external files.
- Arbitrary deck generation from scratch.
- Full PowerPoint GUI automation.
- Collaboration, cloud sync, multi-user accounts and hosted execution.
- Audio/video/OLE/SmartArt semantic editing unless explicitly supported by a later adapter.

## 5. Functional requirements

### FR-01 Input validation

The system MUST accept only a valid `.pptx` file for MVP input, reject corrupt or unsupported files with a user-readable error, and never modify the uploaded original in place.

### FR-02 Job isolation

Each request MUST run in an isolated job directory containing the original, working copy, plan, checkpoints, previews, logs and final artifacts.

### FR-03 PPTX inventory

The system MUST inventory slide index, shape type, object name, text runs, bounding box, z-order, placeholder metadata, group membership, table/chart presence and media references where available.

### FR-04 Plan contract

The agent MUST return schema-valid JSON operations. An operation MUST identify target scope, action, parameters, preservation rules, confidence and expected postconditions. Free-form code is not a valid plan output.

### FR-05 Execution safety

The executor MUST apply only allowlisted operations and reject unknown actions, missing targets, out-of-scope targets, malformed values and unsafe paths.

### FR-06 Preservation

Unless explicitly targeted, the executor MUST preserve slide count, untouched object properties, theme references, master/layout relationships, media relationships and speaker notes as far as the selected editing backend supports.

### FR-07 Verification

The system MUST re-parse the output, compare it with the input and plan, render changed slides, and report structural or visual defects before the result can be marked accepted.

### FR-08 Human review

The system MUST require review when confidence is below threshold, the target is ambiguous, a visual-only judgment is required, a repair loop repeats, or preservation cannot be proven.

### FR-09 Runtime adapter

Each agent CLI adapter MUST expose installed/version/auth status, run a bounded task in the job workspace, stream progress, capture exit code/stderr and support cancellation where the CLI permits.

### FR-10 Artifact delivery

An accepted job MUST expose the final editable PPTX, preview images/PDF, edit plan, verification result and a human-readable summary.

## 6. Non-functional requirements

- Local execution and local artifact storage by default.
- Linux, macOS and Windows support for the application shell; runtime-specific limitations are visible.
- No API-key field or app-managed provider secret.
- Deterministic executor behavior for the same plan and input.
- Job cancellation and cleanup.
- No shell access for the agent outside the isolated workspace and allowlisted tools.
- Structured logs without credentials or raw secrets.
- A single-slide edit should provide a first preview within 60 seconds on a reference development machine, excluding slow agent startup.

## 7. Error and status contract

| Condition | HTTP/status category | Required behavior |
|---|---:|---|
| Unsupported extension | 400 | Reject before job creation. |
| Invalid/corrupt PPTX | 422 | Explain validation failure; retain original. |
| Missing or ambiguous target | 422 | Ask for clarification or offer review. |
| No authenticated runtime | 424 | Show runtime setup instructions; do not request API key. |
| Agent timeout/cancel | 408/499 | Preserve checkpoint and expose retry/cancel state. |
| Plan schema failure | 422 | Do not execute; capture validation evidence. |
| Unsupported edit operation | 409 | Mark `needs_review`; do not approximate silently. |
| Render failure | 502 | Preserve output checkpoint; report renderer diagnostics. |
| Unexpected executor failure | 500 | Roll back to last valid checkpoint and redact logs. |

## 8. Acceptance criteria

- [ ] A valid PPTX can be uploaded without changing the source file.
- [ ] A natural-language request produces a schema-valid plan or a clarification request.
- [ ] A supported text edit changes only the intended target.
- [ ] A missing/ambiguous target never causes a guessed edit.
- [ ] The output opens as an editable PPTX after save and render round-trip.
- [ ] Structural diff reports intended and unintended changes.
- [ ] Preview and QA evidence are visible before download.
- [ ] No provider API key is requested, stored or logged.
- [ ] At least one CLI adapter works with an existing authenticated login.

## 9. Boundaries

### Always

- Preserve the original input and create checkpoints.
- Validate all plans and file paths.
- Run structural and render verification before claiming success.
- Redact secrets and machine-specific credential paths from logs.
- Keep the spec and evidence current.

### Ask first

- Adding a new provider/runtime adapter.
- Changing public API contracts or job persistence schema.
- Enabling GUI automation or external network access.
- Supporting unsupported object types through a lossy fallback.
- Adding reference-document ingestion.

### Never

- Never embed or request provider API keys.
- Never execute arbitrary agent-generated shell commands on the host.
- Never overwrite the original PPTX.
- Never silently claim visual fidelity without render evidence.
- Never commit credentials, cookie exports or raw local secrets.

## 10. Open decisions

- Initial local API framework: FastAPI or Node.
- Initial agent runtime priority: Codex, Gemini CLI or Claude Code.
- Renderer baseline: LibreOffice only or optional native PowerPoint verification on Windows.
- Exact supported MVP operation vocabulary.
