# Lumira sections 4–10 detailed requirement mapping
Date: 2026-11-13
Parent audit: docs/lumira_full_scope_mapping_audit_2026-11-13.md

## Section 4 — Core architecture and Main Brain
Requirement groups: core application architecture; Main Brain; service/module/feature registries; feature activation/deactivation; config/environment; lifecycle; API gateway; inter-service communication; event bus; queues; scheduler/background jobs; state/session/context; dependency injection; plugin loader; health; shutdown/restart; startup/error handling.
Candidate source: app/core/, app/services/brain/, features/, providers/, lifecycle/, system/, app/main.py, app/router_registry.py.
Evidence: LumiraCore/BrainService pipeline; shared service registry; SystemStatus aggregates bounded health probes; focused health tests 12 passed on 2026-11-12.
Gaps: requirement-level traceability, dependency injection and lifecycle coverage, scheduler/event bus/queue end-to-end proof, startup/degraded/restart acceptance.
Acceptance: clean startup, health and degraded status, activation, failure isolation, graceful shutdown/restart and one representative end-to-end Brain run.
Status: IN_PROGRESS.

## Section 5 — Intelligence and reasoning
Requirement groups: NLU; intent/context; entities/relationships; ambiguity; goals; multi-step reasoning; planning/decision; constraints/risk; decision history; self-evaluation; output verification; uncertainty/hallucination control; structured output; tool selection; model routing/collaboration; context/token/resource management; fallback.
Candidate source: app/services/brain/, reasoning/, decision/, context/, validation/, verification/, multi_model/, app/agents/.
Tests to trace: tests/test_lumira_core_brain.py, tests/test_brain_execution_coordinator.py, tests/test_command_conversation_routing.py, tests/test_pipeline_guard.py and relevant context/decision suites.
Gaps: atomic requirement/test mapping, adversarial ambiguity set, calibrated uncertainty, independent output verification, context/token budget acceptance.
Acceptance: fixed test cases for English/Tamil/mixed inputs; ambiguity asks clarification; uncertainty explicit; rejected plan never executes.
Status: IN_PROGRESS.

## Section 6 — Model and provider management
Requirement groups: local model discovery/install/remove/update/version/config/health/capability/benchmark; CPU/RAM/GPU detection; resource-aware selection; local/cloud/hybrid; provider registry/auth/secrets/usage/rate limits/failure/fallback/comparison/cost.
Candidate source: app/services/providers/, multi_model/, resources/, provider startup registration and provider tests.
Evidence: provider registry and central access policy; previous local Ollama and Faster-Whisper operation. Readiness is registration/configuration, not successful inference or reachability.
Gaps: provider lifecycle manager, resource-aware routing, per-provider usage/cost telemetry, bounded health probes, live provider tests.
Acceptance: locality/consent enforced before each call; no call in Offline mode; failures are truthful; heavy models deferred under memory pressure.
Status: IN_PROGRESS; live provider acceptance BLOCKED by config/consent.

## Section 7 — Memory and knowledge intelligence
Requirement groups: working/short/long-term; episodic/semantic/personal/project/preference/conversation/experience memory; indexing/embeddings/vector store; contextual/relationship retrieval; relevance/prioritization/consolidation/dedupe/correction/evolution; retention/provenance; export/import/backup/recovery; knowledge graph/entities/relationships/query.
Candidate source: app/services/memory/, persistence/, knowledge/, memory/, data/.
Tests to trace: tests/test_memory_lifecycle.py, tests/test_memory_evolution_route.py, tests/test_data_backup_service.py and knowledge/memory suites.
Evidence: JSON-backed memory, memory lifecycle/evolution, artifact links and backup/restore tests.
Gaps: full graph/vector backend, relationship-aware retrieval, retention/deletion and end-to-end cross-restart acceptance.
Acceptance: save/retrieve/correct/consolidate/export/restore/delete with provenance and access isolation.
Status: IN_PROGRESS.

## Section 8 — Personal knowledge library
Requirement groups: PDF/Word/spreadsheet/presentation/image/scan/audio/video metadata/transcript ingestion; OCR/extraction; classification/metadata/chunking/indexing/embeddings/RAG/citations/provenance/collections/versioning/cross-document search/project-memory linking.
Candidate source: app/services/knowledge/, documentation/, data/, search/, artifacts/, routes/.
Evidence: document ingestion and PDF extraction dependencies; focused text/Markdown/JSON/CSV/HTML/PDF tests recorded.
Gaps: Office formats, OCR/scanned PDFs, image/presentation extraction, audio/video ingestion, citation fidelity and large-library tests.
Acceptance: each supported format ingests with limits; citations point to source; persisted searchable content survives restart; malformed files fail safely.
Status: IN_PROGRESS.

## Section 9 — Multi-agent intelligence
Requirement groups: agent creation/roles/identity/capability registry/templates/allocation/scheduling/execution; communication/shared context/state; parallel/sequential collaboration; delegation; conflict handling; result consolidation; performance/supervision/permissions/termination/recovery; specialist roles: research, coding, electronics, engineering, planning, data analysis, project management, IoT, robotics.
Candidate source: app/agents/, app/services/multi_agent/, autonomy/, background_tasks/, brain/.
Evidence: agent orchestration, sequential workflow dispatch, registered-agent discovery/dispatch, bounded background task queue.
Gaps: nine specialist role contracts, true parallelism, shared-state isolation, conflict resolution, scheduling, run budgets and recovery acceptance.
Acceptance: delegate to constrained agents; merge traceable results; recover failures; prove no permission escalation or budget bypass.
Status: IN_PROGRESS.

## Section 10 — Workflow and automation
Requirement groups: natural-language workflow creation; templates; visual designer; execution; scheduling; event/time triggers; conditions/loops/dependencies; persistent state/history/monitoring; failure/retry/recovery/cancel/pause/resume; human approval; permissions/versioning/testing.
Candidate source: app/services/workflow/, workflow_recovery/, execution/, planner/, routes/.
Evidence: persisted WorkflowEngine stage records, resume validation, cancellation/recovery and Brain preflight tests.
Gaps: recurring scheduler, event triggers, visual designer, loop semantics, approval UX, versioning and complete automation test harness.
Acceptance: create→validate→run→pause/cancel→resume/recover; persisted history; bounded/idempotent side effects.
Status: IN_PROGRESS.

## Mapping result
Sections 4–10 are now described at requirement-group level with candidate code/test surfaces, existing evidence, gaps and acceptance criteria. This is a detailed scope map, not proof every nested prompt item has been implemented. The authoritative JSON ledger still needs per-row dependency, external dependency, security classification and test evidence fields. Keep all 173 existing prompt rows IN_PROGRESS until individually mapped and tested.
