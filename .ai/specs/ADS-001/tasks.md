# Tasks: AutoSlide MVP and Roadmap

**Spec ID:** ADS-001  
**Status:** DRAFT — Gate #0 pending

## Phase 0 — Repository and governance

- [ ] `[Slice: foundation-runtime]` Confirm repo branch/remote setup and add project documentation. **Depends:** none. **Owner:** orchestrator. **Verify:** `git status`, remote check, documentation review.
- [ ] `[Slice: foundation-runtime]` Add development commands, environment policy and contribution rules. **Depends:** first task. **Owner:** coding. **Verify:** clean docs review.

## Phase 1 — Foundation runtime

- [ ] `[Slice: foundation-runtime]` Implement job state model and per-job workspace manager. **Depends:** Phase 0. **Owner:** coding. **Verify:** unit tests for create, checkpoint, cancel and cleanup.
- [ ] `[Slice: foundation-runtime]` Implement runtime adapter contract and detection for Codex/Gemini/Claude CLI. **Depends:** job model. **Owner:** coding. **Verify:** mocked detection and auth-status tests.
- [ ] `[Slice: foundation-runtime]` Implement redacted event logging and resumable state. **Depends:** job model. **Owner:** coding. **Verify:** secret-redaction and interrupted-job tests.

## Phase 2 — PPTX ingest

- [ ] `[Slice: pptx-ingest]` Validate PPTX OPC package and reject invalid inputs. **Depends:** workspace manager. **Owner:** coding. **Verify:** valid/corrupt/unsupported fixtures.
- [ ] `[Slice: pptx-ingest]` Build slide/object/run inventory and composite object fingerprints. **Depends:** validation. **Owner:** coding. **Verify:** fixture manifest snapshots.
- [ ] `[Slice: pptx-ingest]` Produce slide thumbnails and inventory metadata. **Depends:** inventory. **Owner:** testing/coding. **Verify:** thumbnail count and dimensions.

## Phase 3 — Edit planner

- [ ] `[Slice: edit-planner]` Define versioned TaskPlan JSON schema and operation vocabulary. **Depends:** ingest manifest. **Owner:** architect/coding. **Verify:** schema validation fixtures.
- [ ] `[Slice: edit-planner]` Implement prompt payload builder with target scope and preservation policy. **Depends:** schema. **Owner:** coding. **Verify:** golden prompt payload tests.
- [ ] `[Slice: edit-planner]` Implement policy gate for unknown operations, ambiguity and low confidence. **Depends:** schema. **Owner:** coding/security. **Verify:** rejection matrix.

## Phase 4 — PPTX executor

- [ ] `[Slice: pptx-executor]` Implement run-level text replacement preserving formatting. **Depends:** TaskPlan and fingerprints. **Owner:** coding. **Verify:** formatting-preservation fixtures.
- [ ] `[Slice: pptx-executor]` Implement supported shape position/size and basic formatting operations. **Depends:** text executor. **Owner:** coding. **Verify:** geometry snapshots.
- [ ] `[Slice: pptx-executor]` Implement checkpoint, package validation and structural diff. **Depends:** executor operations. **Owner:** coding/verifier. **Verify:** untouched-object diff tests.
- [ ] `[Slice: pptx-executor]` Add XML fallback for explicitly supported advanced operations. **Depends:** structural diff. **Owner:** coding. **Verify:** round-trip fixtures.

## Phase 5 — Quality gates

- [ ] `[Slice: quality-gates]` Implement isolated LibreOffice/Poppler render adapter. **Depends:** valid output checkpoint. **Owner:** testing. **Verify:** render smoke tests per OS target.
- [ ] `[Slice: quality-gates]` Implement structural acceptance gate. **Depends:** diff engine. **Owner:** verifier. **Verify:** intentional and collateral-change fixtures.
- [ ] `[Slice: quality-gates]` Implement visual findings contract and overflow/clipping checks. **Depends:** renderer. **Owner:** verifier. **Verify:** defect fixtures and evidence images.
- [ ] `[Slice: quality-gates]` Implement bounded repair loop and human-review transition. **Depends:** both gates. **Owner:** coding/verifier. **Verify:** max-attempt and repeated-failure tests.

## Phase 6 — Local workbench

- [ ] `[Slice: local-workbench]` Implement upload/instruction/job creation UI. **Depends:** job API. **Owner:** frontend.
- [ ] `[Slice: local-workbench]` Implement progress stream, preview and findings view. **Depends:** quality-gates API. **Owner:** frontend.
- [ ] `[Slice: local-workbench]` Implement approval/rejection and artifact download. **Depends:** preview. **Owner:** frontend.
- [ ] `[Slice: local-workbench]` Run cross-platform local smoke test. **Depends:** all UI tasks. **Owner:** testing.

## Phase 7 — Reference ingestion (deferred)

- [ ] `[Slice: reference-ingestion]` Define Source Fact Graph and provenance schema. **Depends:** Phase 6. **Owner:** architect/coding.
- [ ] `[Slice: reference-ingestion]` Add DOCX/XLSX/PDF/image extractors. **Depends:** schema. **Owner:** coding.
- [ ] `[Slice: reference-ingestion]` Add source-grounded table/chart updates and semantic parity gate. **Depends:** extractors and executor. **Owner:** coding/verifier.

## Phase 8 — Packaging (deferred)

- [ ] `[Slice: cross-platform-packaging]` Add prerequisite diagnostics and installer flow. **Depends:** Phase 6. **Owner:** release/testing.
- [ ] `[Slice: cross-platform-packaging]` Add optional native Windows verification adapter. **Depends:** quality gates. **Owner:** coding/testing.
- [ ] `[Slice: cross-platform-packaging]` Produce release checklist and smoke-test evidence. **Depends:** installer. **Owner:** ship/verifier.

## Verification gates

- **Gate 0:** user approves capability map, requirements and design before coding.
- **Gate 1:** each phase passes its exit gate and updates `SESSION_STATE.json`.
- **Gate 2:** verifier confirms structural/visual evidence and sanitizer checks.
- **Gate 3:** release packaging passes cross-platform smoke tests.
