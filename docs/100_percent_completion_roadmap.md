# Lumira 100% Completion Roadmap

**Status:** Active engineering plan; not a completion claim
**Baseline:** Current local checkout on `main`, with pre-existing uncommitted changes
**Rule:** Preserve all existing source edits, user data, memory, artifacts, and configuration. Never commit runtime state files.

## 1. Definition of 100% complete

Lumira is complete only when every capability in the agreed scope:
1. Has a defined user-visible behavior and explicit acceptance criteria.
2. Is implemented in the backend and exposed through the real desktop experience where applicable.
3. Handles invalid input, missing providers, timeouts, cancellation, restart, and partial failure safely.
4. Has unit, route, integration, and UI tests appropriate to its risk.
5. Passes real user-journey testing in the packaged Windows application.
6. Has no dead controls, fabricated outputs, placeholder success, hidden blockers, or misleading status.
7. Has documented dependencies, permissions, setup, data location, and known limitations.

A passing unit test or an existing route alone never earns a feature-complete status. External providers, models, microphones, hardware, credentials, and OS isolation must be tested separately. If a required dependency is unavailable, the feature remains visibly unavailable—not falsely complete.

## 2. Scope inventory: the current 28-feature registry

The existing `docs/feature_completion_matrix.md` defines these 28 registry entries. Preserve these IDs unless a deliberate migration is designed.

1. Memory
2. Voice input
3. Voice idea capture
4. Artifact manager
5. Image generation
6. Unified search
7. Intent
8. Goals
9. Planner
10. Agents
11. Learning
12. Sessions
13. Projects
14. Code
15. Workflows
16. Autonomous development
17. Recovery
18. Image understanding
19. Web access
20. Research
21. Device management
22. Mode management
23. Terminal
24. Project preview
25. Notepad
26. Capability system
27. Security
28. Observability

The broader product scope also includes the Handoff 10 requirements: Lumira identity, feature activation, Tamil/English/mixed-language support, voice idea capture, audio storage/playback, transcripts, idea summaries, expanded memory, artifact management/storage, image generation, and unified search. Map each requirement to the 28 registry entries and add explicit acceptance criteria where the current matrix does not cover it. Do not invent additional registry entries or silently drop requirements.

## 3. Release-blocking engineering work

### A. Protect and establish a reproducible baseline
- Preserve the current uncommitted changes and modified runtime JSON.
- Record the current branch, commit, dirty-file list, Python/Node versions, package-lock state, and available RAM.
- Separate source/configuration from runtime data; ensure backup/restore and migration behavior.
- Create a clean, reproducible test procedure that does not overwrite the active checkout or user data.
- Keep a clear source-only commit allowlist; never commit memory, recordings, API keys, tokens, local model files, or generated private artifacts.

### B. One provider and permission architecture
- Trace every provider from application startup and registry to the actual user request and final response.
- Define one central provider contract: capabilities, readiness, health, configuration, timeout, cancellation, errors, usage and privacy.
- Enforce Offline / Hybrid / Cloud policy centrally for chat, vision, image generation, transcription, speech, research, embeddings and every network-backed modality.
- Offline must make no unintended cloud calls. Hybrid must prefer local and use cloud only after explicit user consent. Cloud must still require valid provider configuration and clear user selection.
- Keep cloud disabled by default and preserve the user's existing Offline setting.
- Test provider missing, invalid key, unavailable host, timeout, malformed response, rate limit, cancellation and recovery.
- Distinguish configured, registered, reachable and successfully tested states.

### C. Complete the desktop application
- Verify every page, navigation item, setting, modal, menu, button, form, empty state and error state against its backend contract.
- Remove dead buttons and fake/demo responses; wire each control to a real action or mark it explicitly unavailable.
- Verify loading, retry, cancellation, validation, accessibility, keyboard navigation and responsive layout.
- Verify conversation rendering for plain text, Markdown, code, JSON-like content, images, audio, video, files, tool activity and errors; never leak raw internal JSON as the user-facing answer.
- Verify chat history creation, rename, search, delete, persistence and recovery.
- Verify settings persistence and restart behavior.
- Test Electron preload/IPC boundaries, API proxy, process lifecycle, local backend startup/shutdown, logs and error recovery.
- Build and launch the packaged Windows installer on the target laptop; test upgrade, first launch, restart, uninstall/reinstall and data preservation.

### D. Brain, orchestration and agent execution
- Preserve Lumira identity and deterministic pipeline: validate → builder → execute → code → memory → learn.
- Enforce explicit state transitions, stop on rejection, no skipped stages, no false completion, and auditable checkpoints.
- Add bounded run deadlines, cancellation propagation, retry budgets, idempotency and cleanup, adapting Leon's agent-run-budget and tool-execution patterns.
- Add tool permission policies, argument schemas, output bounds, progress events and user approval for consequential actions.
- Add safe context assembly and token budgeting; keep durable memory retrieval distinct from conversation context.
- Add failure recovery and resume tests for every stage; recovery must not repeat unsafe side effects.
- Agent delegation must be explicit, bounded, observable and unable to bypass the Brain's gates.

### E. Memory, sessions, artifacts and search
- Verify memory create/read/update/delete, deduplication, provenance, confidence, retention and restart persistence.
- Ensure learning stores only verified experiences and never turns unverified model output into trusted memory.
- Verify session lifecycle, history, branching/continuation if promised, interrupted sessions and recovery.
- Verify artifact metadata, binary integrity, size/type limits, ownership, indexing, search, playback/viewing, export, deletion and corruption handling.
- Ensure audio recordings, transcripts, summaries and images are stored only under explicit user-approved retention rules.
- Make unified search cover projects, memory, artifacts, sessions and conversation history with source labels, ranking, permissions and deletion consistency.
- Test backup, restore, migration and index rebuild without losing user data.

### F. Voice and language
- Complete microphone permission/device discovery, capture, stop, interruption, playback and clear unavailable-device states.
- Complete wake-word activation only when the configured engine and model are installed; never pretend wake-word detection is active otherwise.
- Complete voice idea capture in Tamil and English; store audio, transcript and summary as linked artifacts with timestamps and user controls.
- Verify transcription locally and/or through the selected remote provider, including long recordings, silence, noise, corrupt audio and provider failure.
- Test Tamil Unicode, romanized Tamil, English and Tamil-English mixed requests against real workflows—not just language labels.
- Verify text-to-speech, voice selection, playback controls and interruption if voice output is part of the promised experience.

### G. Multimodal and knowledge capabilities
- Image generation: real configured provider, prompt validation, progress, output file, artifact persistence and failure handling.
- Image understanding: local/remote routing, bounded image inputs, real model result, optional report artifact and privacy controls.
- Documents/RAG: safe ingestion, extraction, chunking, embeddings, retrieval, citations/source locations, update and deletion.
- Research/web: bounded requests, source attribution, redirect/DNS protections, timeouts, rate limits and explicit unavailable states.
- Video/audio: only expose operations supported by a real configured provider; validate upload limits, playback and artifact lifecycle.
- Do not claim a modality is operational merely because a provider interface exists.

### H. Projects, code, workflows and autonomous development
- Verify project create/list/open/update/version/export/delete and authorization boundaries.
- Verify generated code files, diffs, validation, rollback and project metadata.
- Make workflow dependencies, status transitions, retries, cancellation, checkpoints and duplicate prevention deterministic.
- Autonomous development must produce a bounded plan, inspect files, make scoped changes, run relevant tests, report exact diffs and stop on safety violations.
- Project preview must actually launch and supervise an isolated preview process if that is promised; a saved loopback URL is not process launch.
- Keep arbitrary terminal execution disabled until a real per-run OS sandbox is installed and independently verified for filesystem, network, CPU, memory, process, timeout and cleanup boundaries.

### I. Plugins, skills, tools and integrations
- Design a declarative manifest with identity, version, entrypoint, declared capabilities, schemas, settings, permissions and compatibility.
- Validate manifests and signatures/provenance; maintain an allowlist and explicit user enable/disable controls.
- Add a permission broker and per-tool authorization; external plugin code must not execute in-process without an independently verified sandbox.
- Add lifecycle, event, logging, versioning, uninstall and rollback behavior.
- Adapt PyGPT/AnythingLLM patterns selectively; do not import their entire desktop/runtime stacks.

### J. Security, privacy and reliability
- Review authentication, authorization, token validation, secret storage, rate limiting, CORS, CSRF where applicable, IPC, path traversal, SSRF, uploads and local network exposure.
- Use least privilege and local-only defaults; never log credentials, private prompts or recordings unnecessarily.
- Verify generated-project and plugin isolation before enabling execution.
- Add structured, redacted logs, health checks, diagnostics, crash recovery and actionable error reporting.
- Test corrupted JSON/database state, disk full, permission denied, low RAM, offline startup, provider outage and forced shutdown.
- Provide user-controlled export, deletion and backup/restore behavior.

### K. Packaging, installation and release
- Pin and audit dependencies; record third-party notices and upstream revisions for copied/adapted code.
- Keep optional heavy dependencies optional; do not install all AI runtimes/models by default.
- Verify Windows installer, paths with spaces/non-ASCII characters, first-run setup, backend lifecycle, logs, updates and rollback.
- Verify user data survives application upgrades and is not overwritten by source updates.
- Produce a release checklist, changelog, known limitations and recovery instructions.

## 4. Mandatory verification gates

1. Static checks: Python syntax/type/lint where configured; TypeScript build; frontend lint; dependency/license audit.
2. Unit tests: all services, providers, state machines and utilities.
3. API tests: validation, authorization, persistence, error and unavailable-provider behavior.
4. Integration tests: real backend-to-provider and backend-to-desktop contracts.
5. UI tests: every primary route and high-risk user journey.
6. Security tests: SSRF, path traversal, secret redaction, auth boundaries, IPC and sandbox escape attempts.
7. Data tests: migration, corruption recovery, backup/restore and deletion consistency.
8. Packaged-app tests: install, launch, chat, settings, voice, artifacts, restart, update and uninstall.
9. Hardware/provider tests: actual microphone, speakers, chosen model/provider and connected devices.
10. Acceptance sign-off: each registry entry has evidence, environment, date, result and remaining constraints.

## 5. Recommended build sequence

**Phase 0 — Baseline and protection:** clean inventory, backups, dirty-worktree protection, dependency/runtime facts, test harness.

**Phase 1 — Core correctness:** chat response rendering, normal chat routing, provider registry, central Offline/Hybrid/Cloud policy, settings persistence and packaged desktop API bridge.

**Phase 2 — Brain reliability:** state machine, run budgets, cancellation, tool policies, checkpoints, retries and recovery.

**Phase 3 — Data foundation:** memory, sessions, artifacts, unified search, backup/restore and migrations.

**Phase 4 — Core user experience:** desktop navigation, conversation history, settings, Notepad, goals, planner, projects and observability.

**Phase 5 — Voice and language:** capture, audio storage/playback, transcription, summaries, Tamil/English/mixed-language acceptance and optional wake word/TTS.

**Phase 6 — Multimodal and knowledge:** image generation/understanding, document ingestion/RAG, research/web and supported video/audio operations.

**Phase 7 — Automation and extensibility:** agents, workflows, autonomous development, plugin/skill manifests and permission broker.

**Phase 8 — Secure execution and devices:** sandbox provider, project preview process supervision, terminal execution only after isolation verification, hardware/device integrations.

**Phase 9 — Release hardening:** full regression, security, performance/resource tests, packaged Windows acceptance, backup/restore, upgrade and release documentation.

Phases may overlap only when dependencies and acceptance gates are clear. Do not skip a blocking gate to increase a completion percentage.

## 6. Definition of done per feature

Each feature must have:
- User journey and acceptance criteria.
- Backend implementation and registered capability.
- Desktop UI wired to the real backend.
- Unit + API + integration + UI regression coverage.
- Missing-provider and failure behavior.
- Security/privacy review proportional to risk.
- Real environment evidence where hardware, provider, model or packaging is involved.
- Documentation and third-party notices.
- No unresolved critical/high-severity defects.

## 7. Current known blockers from the latest audit

- The desktop suite had 31 passing tests, lint had zero warnings/errors, and the frontend production build passed. These results cover the audited worktree at that point only.
- The packaged Electron application and real user journeys are not yet verified.
- Baseline cloud-consent enforcement was unproven across modalities; the central enforcement implementation and full-suite evidence are recorded in Section 10.
- A complete plugin/skill execution framework was not found.
- Provider registration and actual successful inference still need end-to-end proof.
- Tamil and mixed-language semantic acceptance remains outstanding.
- Project preview currently registers a URL but does not launch a preview process.
- Terminal execution remains intentionally disabled until OS-level isolation is independently verified.
- Real provider, microphone, hardware, resource-pressure, recovery and long-duration tests remain outstanding.
- The current working tree already contains uncommitted source, tests and documentation changes plus modified runtime JSON. Preserve them. Do not reset, clean, stash, or bulk-commit the checkout.

## 8. Immediate next engineering task

COMPLETED 2026-11-04: traced normal chat and provider registry paths, implemented the central fail-closed provider-access boundary, and applied it to chat and every identified provider-backed modality. See the completion evidence in Section 10. The remaining Phase 1 work (conversation rendering, desktop API bridge verification and other core-correctness items) is still open; this record does not mark all of Phase 1 complete.

**Current completion status:** Not yet 100%. This roadmap is the work plan, not evidence that the listed work is finished.


## 9. Provider-policy trace findings — 2026-11-04

Read-only inspection of the active local checkout confirmed:

- `app/main.py` calls `register_configured_providers()` at import/startup.
- `ProviderRegistry` is a simple thread-safe name-to-object registry; it does not carry provider locality, network-use metadata, or a policy decision.
- `ConversationProviderRouter` applies Offline/Hybrid/Cloud rules to ordinary chat only.
- `AIModeService` exposes the persisted policy fields: `local_providers_allowed`, `network_allowed`, and `external_providers_allowed`.
- Direct provider-backed service calls were found in:
  - `ImageGenerationService` → `image_generation`
  - `ImageUnderstandingService` → `image_understanding`
  - `ResearchCapabilityService` → `research`
  - `TranscriptService` → `transcription`
  - `SpeechPlaybackService` → `speech_synthesis`
  - `SummaryService` → `summarization`
- These services retrieve provider objects from `ProviderRegistry` and invoke them directly. The inspected call sites do not consult `AIModeService` before invoking those providers. Therefore the current code does not yet demonstrate universal Offline/Hybrid/Cloud enforcement across all modalities.
- Local implementations identified: Ollama chat, Ollama summary, Ollama vision, and faster-whisper transcription. OpenAI-compatible image/speech/transcription/vision/chat and Tavily research are external by default. Picovoice wake-word processing needs an explicit locality determination from its implementation/configuration before policy classification.
- `ProviderReadinessService` deliberately reports registration, not reachability or successful operation. Preserve that distinction in UI and diagnostics.

**Confirmed blocker:** implement a central, fail-closed provider-access policy with explicit provider locality/network metadata, then enforce it at every provider invocation boundary. Unknown providers must default to external/network-backed and be denied when external access is disabled. Tests must prove Offline makes no external provider calls; Hybrid uses local first and uses external providers only with explicit consent; Cloud requires explicit consent and a configured cloud provider. Keep local provider access blocked in Cloud mode if that remains the defined product policy.

**Test constraint during this trace:** host free RAM was approximately 1.43 GiB. No full backend test suite or heavy model runtime was launched. The previous 31 frontend tests, lint, and production build results remain the only fresh verification evidence from this work session.


## 10. Central provider-access policy ? implementation and verification record

**Status: IMPLEMENTED.** This closes the provider-access-policy work item in Phase 1 (Core correctness). It does not mark the entire Phase 1 or Lumira roadmap complete.

### Policy contract
- `ProviderAccessPolicyService` is the shared authorization boundary. It reads the persisted `AIModeService` policy immediately before provider invocation.
- Providers must explicitly declare `provider_scope` as `local` or `external`. Missing, malformed, or unreadable scope metadata is classified as `external`.
- Policy-store read errors, malformed policy objects, and invalid persisted modes fail closed. A corrupt mode is no longer silently interpreted as Hybrid; a cloud-consent update also cannot silently rewrite a corrupt mode.
- Offline: local providers only; external providers are denied even if an old cloud-consent flag remains saved.
- Hybrid: local providers are used first by the chat router; external providers require the separate explicit cloud-consent setting.
- Cloud: local providers remain blocked; external providers require explicit cloud consent and an instantiated/configured provider.
- Cloud consent remains disabled by default. The implementation does not change the user's saved AI mode or consent setting.

### Enforced invocation boundaries
- Conversation chat: local-first router and consent-gated cloud fallback.
- Image generation and image understanding.
- Research and summarization.
- Audio transcription and speech synthesis.
- Wake-word artifact detection and the background microphone listener (policy checked before microphone startup).
- Video generation.
- Device command transport. Unknown device transports are external by default; a local transport must explicitly declare local scope.
- All built-in provider classes now declare locality metadata. OpenAI-compatible adapters with permitted localhost HTTP endpoints classify from the actual endpoint; public HTTPS endpoints classify as external. Picovoice remains external/blocked without consent until its SDK licensing/network behavior is independently established.

### API behavior
- Policy denials return HTTP 403 at the image, voice, wake-word-listener and device-command routes.
- Policy-store failures return HTTP 503. Existing voice partial-success behavior is preserved for ordinary missing-provider and resource-pressure cases.
- Provider readiness remains a registration signal only; it is not represented as reachability or successful inference.
- Health/readiness responses must expose registration/configuration separately from unprobed reachability and last successful operation; `null` is the truthful value until an explicit, bounded probe exists.

### Verification evidence
- Added policy unit tests for Offline, Hybrid, Cloud, explicit consent, unknown providers and unreadable settings.
- Added deny-before-invocation integration coverage across image generation, image understanding, research, transcription, summarization, speech playback and wake-word artifact activation.
- Added regression coverage for background wake-word startup and device transports.
- Final complete repository test run: **702 passed, 1 skipped, 0 failed** (`python -m pytest -q`, 297.11 seconds). One existing Pydantic serializer warning was emitted by `test_core_feature_contract.py::test_brain_validator_rejects_runtime_corruption_of_mutable_state`; it is unrelated to provider access.

### Remaining boundaries (not claimed complete by this item)
- This is an access-policy boundary, not a full provider lifecycle/health contract. Provider reachability, cancellation propagation, usage metering and operational health checks remain separate work.
- Real remote provider calls, actual microphone hardware, Picovoice SDK licensing behavior, device hardware and packaged desktop journeys require environment-level verification.
- Hybrid local-first fallback is implemented for chat. Other modalities use the explicitly registered provider for that capability; they do not fabricate a local fallback when none is configured.


## 11. Phase 1 / Phase 2 implementation and verification update — 2026-11-05

- Added docs/phase_1_core_correctness.md as the acceptance ledger for roadmap Phase 1. Chat routing/output rendering, provider access policy, persisted AI mode/cloud consent, and desktop API integration have focused backend/UI verification. Packaged app and live provider/hardware acceptance remain open.
- Handoff 10 Phase 2 is tracked separately in docs/phase_2_capability_expansion.md; do not confuse it with roadmap Phase 2 (Brain reliability).
- Brain reliability cross-cutting work now routes both execute() and execute_with_trace() through one bounded path; resume also applies fail-closed retry safety and attempt bounds. Session-scoped cancellation is surfaced in the desktop composer.
- Latest focused verification: backend 99 passed / 0 failed across Phase 1 provider/chat, Phase 2 Handoff 10 capabilities, and Brain execution-control suites; desktop 34 passed / 0 failed across 5 files; lint 0 warnings/errors; production build passed; full Python compileall and git diff check passed.
- These are focused suites, not a full backend repository run. No packaged installer, live provider inference, microphone/speaker/wake-word hardware, live image-generation provider, or visual packaged-app acceptance was performed. OS-level generated-code isolation remains unverified; terminal execution remains disabled.
- Brain cancellation is cooperative between synchronous stages and the registry is process-local. It does not preempt a currently executing provider call and is not a cross-worker cancellation bus.
- Preserve all pre-existing worktree/runtime data. No commit, push, reset, cleanup, package installation, or BIOS/Windows setting change was made.


## Latest focused acceptance update — 2026-11-05

- Expanded combined safe backend regression matrix: **190 passed, 0 failed** across Phase 1, Handoff 10 Phase 2, Brain execution control, provider policy, voice/audio/artifact, memory, search, image-generation route behavior and Tamil/English language guidance/detection. Tests that execute generated project code were deliberately excluded; this is not a full backend suite.
- Desktop Vitest: **34 passed**, lint: **0 warnings / 0 errors**, production build: passed. Python compileall across app/tests and git diff check passed.
- Added protected same-language response guidance for Tamil Unicode, romanized Tamil and Tamil-English mixed input, plus bounded lexicon coverage and clarification behavior for ambiguous romanized Tamil.
- Added a BrainService regression confirming cancelled pipeline runs are persisted as failures and execution-control registrations are released.
- Release blockers remain: packaged Windows installer and upgrade lifecycle, real local/cloud inference, real microphone/speaker/wake-word hardware, live image generation, visual packaged-app acceptance, and independently verified OS isolation for generated-code execution. Do not report 100% release readiness.


- Final API registration smoke test: the real FastAPI application exposes POST /brain/cancel/{session_id}; route test passes. Brain execution-control suite: 12 passed. Latest backend focused matrix count is now 191 passing tests when including this additional API registration check; earlier 190-test combined run remains the broad matrix baseline.


## 2026-11-06 — Phase 4 and Phase 5 implementation continuation

### Phase 4 — Dashboard, Workspace and Agent UI
- Added a Dashboard page with read-only project, goal, workflow, session, agent and artifact overview.
- Added a dedicated Agents page for registered-agent discovery and explicit task dispatch; fixed the API contract to accept an optional registered agent selection.
- Added navigation and UI for Background Tasks and Self-Improvement, completing the Phase 5 desktop surface.
- Full desktop Vitest suite: **38 passed across 5 files**. Desktop lint: **0 warnings / 0 errors**. TypeScript/Vite production build passed.

### Phase 5 — Bounded Autonomous Operation
- Routed dependency-ordered multi-agent workflow steps through BrainAgentOrchestrator; the workflow route no longer directly bypasses the Brain gate via AgentManager.
- Exposed outcome learning patterns, recommendations, adaptive guidance, execution policy and failure guard in a read-only Self-Improvement page. It does not self-edit source or permissions.
- Added a durable user-submitted background agent task queue and /background-tasks API. States are persisted; interrupted jobs are marked on restart and never auto-replayed; results are secret-redacted and bounded.
- Focused backend verification: **23 passed / 0 failed** across background-task service/API, workflow agent execution, agent dispatch contract and outcome-learning tests. Python byte-compilation passed for touched backend files.

### Release and safety boundaries
- Background tasks are explicit one-shot submissions, not a recurring scheduler or distributed worker system. Agent execution is sequential and provider-dependent.
- No live local/cloud model inference, microphone/speaker/wake-word hardware, or live image-generation provider was tested in this phase.
- No packaged Windows installer, upgrade test, or visual packaged-app acceptance was performed. Free RAM was below the 2 GB packaging gate; packaging was intentionally skipped.
- OS-level generated-code isolation remains unverified. Generated project terminal execution remains disabled.
- Existing working-tree changes and runtime data were preserved. No commit, push, reset, cleanup, package installation or BIOS/Windows setting change was made.
- Phase 4 and Phase 5 implementation and focused verification are complete; Lumira is not yet 100% release-accepted.


## 2026-11-06 — Phase 6–8 implementation and acceptance checkpoint

- Added detailed status reports: `docs/phase_6_ai_intelligence.md`, `docs/phase_7_voice_intelligence.md`, and `docs/phase_8_media_intelligence.md`.
- Backend focused regression: **104 passed, 0 failed**. Desktop focused regression: **32 passed, 0 failed**.
- Phase 6: local Ollama endpoint is reachable and two models are installed, but live inference was deliberately not attempted with only about 1.05 GB free RAM. Cloud mode is disabled and cloud chat configuration is absent from the inspected process environment.
- Phase 7: audio input/output endpoints enumerate and `faster-whisper` is installed, but real recording/playback acceptance remains open. Picovoice dependencies, wake-word credentials/model, local transcription enablement and TTS provider configuration are missing.
- Phase 8: image/video artifact contracts and mock-provider tests exist, but no live image provider is configured. Ollama vision model is installed but not activated/inferred. No concrete video-generation provider is implemented/configured; capability returns unavailable rather than fake success.
- Therefore Phases 6–8 are **not complete**. Remaining work depends on safe RAM headroom, provider configuration/consent, a selected video provider, and user-driven hardware acceptance. Do not mark complete based on mocked tests.
- No external provider call, microphone recording, model inference, commit, push, reset, cleanup or user-data deletion was performed.
