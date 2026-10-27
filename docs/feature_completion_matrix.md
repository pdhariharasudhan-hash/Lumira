# Lumira — 28-Feature Completion Matrix

**Purpose:** source-level completion inventory for the 28 catalog entries. This is not a claim that every feature passed runtime tests. Selected backend tests and frontend build/lint have run in Windows Sandbox, but fresh full verification is still pending; Lumira's own generated-project terminal remains disabled until its per-run OS isolation is implemented and verified.

| # | Feature | Implementation surface found | Current state / remaining gate |
|---:|---|---|---|
| 1 | `memory` | `MemoryService`, `/memory`, cognitive memory stores | Core persistence exists; runtime regression suite still needs a safe run. |
| 2 | `voice_input` | Voice capture service and `/voice` routes | Recording/upload path exists; continuous wake-word capture needs optional Picovoice configuration and device testing. |
| 3 | `voice_idea_capture` | Voice capture, transcript service, remote transcription provider, optional local faster-whisper provider | Provider-dependent, but can now run locally without a remote API after the optional dependency/model is installed and `LUMIRA_LOCAL_TRANSCRIPTION_ENABLED=1` is set. First-run model download and actual Tamil/English accuracy remain environment-dependent and unverified. |
| 4 | `artifact_manager` | Artifact manager and `/artifacts` routes | Text/binary storage, bounded persistent relationships, incoming/outgoing relationship lookup, link/unlink endpoints, archive/restore/delete cleanup, and path-free metadata are implemented. Relationship regression tests are in CI; provider/file behavior still needs full verification. |
| 5 | `image_generation` | Image generation service and OpenAI-compatible image provider | Provider-dependent; activation is blocked until image provider is registered. |
| 6 | `unified_search` | Unified search service and `/search` routes | Project/memory/artifact/history search surfaces exist; artifact results now include bounded related-artifact metadata for graph navigation. Source coverage and runtime checks remain. |
| 7 | `intent` | Intent classifier and `/intelligence/analyze` | Deterministic analysis path exists; semantic coverage remains limited and needs tests. |
| 8 | `goals` | Memory-backed goal operations and `/goals` | CRUD/listing exists; verify persistence and validation tests. |
| 9 | `planner` | `PlannerService`, `PlannerModule`, Brain pipeline | Brain-integrated planning exists; execution readiness depends on decision/constraint gates. |
| 10 | `agents` | `AgentManager`, `/agents`, Brain-gated explicit delegation | Experimental; bounded dispatch exists. General requests are not silently delegated. |
| 11 | `learning` | `LearningService`, `LearningModule`, verified-memory consolidation | Learning/reflection path exists; only verified experiences should be consolidated. |
| 12 | `sessions` | Session manager and `/sessions` | Durable lifecycle/recovery exists; persistence and restart tests remain unrun. |
| 13 | `projects` | Project writer/discovery and project routes | Project creation/inspection/version surfaces exist; generated-project authorization still needs deployment hardening. |
| 14 | `code` | Code service and `/code` route | Code generation/modification exists; executing generated code/tests remains gated by OS isolation. |
| 15 | `workflows` | Workflow engine, work items, `/workflows` | Durable tasks and workflow state exist; behavioral tests remain unrun. |
| 16 | `autonomous_development` | Autonomous development coordinator, bounded backlog/audit/worker services | Source implementation exists; do not claim verified end-to-end development until safe behavioral checks are possible. |
| 17 | `recovery` | Recovery service and `/recovery` | Guarded resume/checkpoint APIs exist; recovery tests remain unrun. |
| 18 | `image_understanding` | Remote vision provider, optional local Ollama vision provider, service, `/images/analyze`, desktop Image Analysis page, optional Artifact Manager report persistence | Can use the remote OpenAI-compatible provider or local Ollama (`LUMIRA_OLLAMA_VISION_ENABLED=1`, default model `moondream`). `save_artifact: true` stores a JSON report with prompt, model, description, timestamp, and an image SHA-256 fingerprint; it does not store the original image and defaults off. Local mode requires Ollama and a pulled vision model; image analysis remains subject to the resource-pressure gate. Actual model behavior and frontend/backend runtime are unverified. |
| 19 | `web_access` | Web resource service and `/web` | Bounded fetch, redirect revalidation, proxy bypass, secret-redacted HTTP(S) link filtering, successful-response-only binary artifacts, and a connect-time public-IP-pinning transport are implemented. Regression tests cover DNS rebinding and connecting to the validated IP, but those tests still need a fresh isolated runtime run. The transport depends on a private httpcore pool hook and fails closed if its expected shape changes; do not expose arbitrary URL fetch to untrusted users until the runtime gate passes. |
| 20 | `research` | Research capability and Tavily provider | Provider-dependent; activation reports missing provider instead of implying live research is ready. |
| 21 | `device_management` | Device gateway and `/devices` | Device registry/status path exists; actual hardware integrations require device-specific verification. |
| 22 | `mode_management` | Mode registry/detection and `/modes` | Mode discovery and session-persisted selection exist; mixed-language semantic detection remains limited. |
| 23 | `terminal` | Project terminal route/service | Intentionally blocked. A Boolean/environment flag cannot enable it; genuine verified OS-level isolation is still missing. |
| 24 | `project_preview` | `ProjectPreviewService` and `/projects/{project}/{version}/preview` (GET/POST), `/projects/{project}/{version}/preview/stop` (POST) | Safe loopback-only preview registration and stop/get persistence exist; this registers a URL but does not launch a preview process. Runtime/browser coverage remains.
| 25 | `notepad` | Persistent Notepad service and `/notepad` | Atomic JSON persistence and CRUD exist; runtime tests remain unrun. |
| 26 | `capability_system` | Capability router and command integration | Broad capability routing exists; keep changes scoped because the router is large and highly coupled. |
| 27 | `security` | Local auth boundary, strict local/generated bearer-token claim validation, bearer-header size bounds, secret redaction, feature lifecycle guards | Token claim shape and timestamp types plus oversized generated bearer headers are rejected at source level; deployment still needs deliberate key provisioning, shared transactional user storage, shared rate limiting, and app-specific authorization. New auth regression tests remain unrun. |
| 28 | `observability` | Pipeline history and `/intelligence/status`, `/intelligence/history` | Status/history surfaces exist; runtime verification remains. |

## Cross-feature blockers

1. **Behavioral verification:** isolated Windows Sandbox runs have succeeded for selected checks, but the current worktree still needs a fresh complete verification. The focused recovery/agent suites passed 43 tests in isolation. The recorded full backend run was 355 passed / 1 failed because the copied workspace's earlier provider-startup subprocess hit a 60-second timeout. The provider-startup test has since been rewritten to exercise registration in-process and cover invalid optional-provider configuration, but that revision has not been rerun. The desktop build and lint passed in an earlier sandbox run; Vitest did not run because that harness passed an unsupported `--minWorkers` option. The harness was corrected to `--maxWorkers=1`, but Vitest has not yet been rerun. Static checks do not substitute for fresh behavioral verification.
2. **Terminal execution:** remains disabled until a real OS sandbox is implemented and independently verified. Do not bypass this with environment variables or UI changes.
3. **Optional providers:** remote transcription, speech synthesis, image generation, remote image understanding, summarization, research, and wake-word detection require explicit local configuration. Optional local transcription uses faster-whisper and a separately downloaded model; optional local image understanding uses Ollama and a separately pulled vision model. No live provider call was made during this work.
4. **Generated project security:** before deployment, provision signing keys and users deliberately, use shared rate limiting if multi-worker, and validate authorization within each generated application.
5. **Hardware:** device records and interfaces do not establish that a physical device was connected or tested.

## Latest changes in this session

- Added `FasterWhisperTranscriptionProvider`, an optional local speech-to-text adapter built against the public `faster-whisper` API. It lazily loads a CPU/int8 model, bounds audio/transcript sizes, respects the resource-pressure gate, and keeps recordings local. Added `requirements-local-transcription.txt`, setup guidance, and an MIT third-party notice. It has not been installed or runtime-tested.
- Added `OllamaVisionProvider` using Ollama's loopback-only native `/api/chat` API for local image understanding, with image/prompt/response bounds and a conservative default model. It is opt-in and takes precedence over remote vision when enabled. Added setup guidance and an MIT third-party notice; model quality and runtime behavior are unverified.
- Workflow checkpoint safety now redacts capability results before placing them in downstream stage context, and explicit blocked/failed/pending/running states cannot be marked complete merely because `success: false` was omitted. Regression tests were added; static compilation passes, but the behavioral tests are not yet run because the current host cannot verify OS isolation and has limited free RAM.
- Feature activation now checks actual registration of required transcription, image-generation, image-understanding, and research providers in addition to dependency readiness.
- Optional provider startup registration now catches expected configuration/type/filesystem errors per provider, logs only provider name and exception type, and leaves the misconfigured provider unavailable without taking down the core API. Regression coverage includes an invalid image-provider URL alongside a valid transcription provider; the test has not yet been executed.
- Added an OpenAI-compatible vision adapter, `ImageUnderstandingService`, `POST /images/analyze`, and a desktop **Image Analysis** page with image upload/prompt/result states.
- Added backend and frontend regression tests for provider readiness, image-analysis validation, and UI submission. Tests have been authored but not executed.
- The Feature Control Center now keeps provider/dependency blockers visible for disabled or degraded features, and labels the aggregate correctly as readiness-blocked.
- Generated API CRUD now returns stable SQLite primary keys and updates/deletes by the actual ID plus owner, avoiding list-position confusion after deletions. Generated auth persists user hashes and its signing key locally, but each worker keeps a process-local user cache and rate-limit counters; multi-worker deployment still needs shared transactional user storage/cache coordination and shared rate limiting.
- Static checks: 306 readable Python files parsed successfully; two existing `__init__.py` files could not be read due to Windows access-denied errors; all 17 `memory/*.json` files parsed; the feature registry contains 28 entries; `git diff --check` passed.


## Current safety follow-up — 2026-10-18

- Command results now fail closed for malformed status/state values and non-terminal states such as `running` or `pending`, including contradictory `success: true` flags.
- Learning consolidation now requires an explicitly verified experience that already exists in durable cognitive memory, uses the persisted record as its source of truth, and avoids creating duplicate learning records for the same experience.
- Static syntax and integration-audit checks pass, but these new regression cases remain unexecuted until verified OS-level isolation is available. The read-only audit reports zero active integration findings but correctly keeps completion blocked.


## Essentials checkpoint — 2026-10-19

- A fresh read-only scan parsed 306 readable Python files under `app/` and `tests/`; two `__init__.py` files remained unreadable due to Windows access-denied errors. All 17 `memory/*.json` files plus `lumira_desktop/package.json` parsed successfully. `git diff --check` passed.
- The current terminal service checks both the hardcoded-disabled flag and a verifier that returns false before reaching `subprocess.run`. Keep it disabled until real OS-level isolation is independently verified.
- No current-worktree behavioral or desktop build/lint result is available. The existing audit report is an earlier read-only snapshot, not proof that the current worktree is complete.
- Priority order remains: verified OS isolation; backend pytest + desktop Vitest/build/lint and failure repair; generated-app deployment hardening; isolated runtime verification of the connect-time DNS-pinning transport; optional provider/device end-to-end tests with credentials/hardware available.
- The persisted feature registry was checked without importing project code: all 28 entries passed status/`enabled`, `feature_id`, and dependency-reference invariants (**0 findings**). Three features are enabled; no additional features were bulk-enabled.
- Read-only persisted-state check: all 80 indexed artifacts exist within the workspace, and all 25 work-item workflows have unique IDs, valid task statuses, and resolvable dependencies (**0 findings**). No memory/state records were modified.


## Continued essentials checkpoint — 2026-10-19

- Preview persistence now fails closed when `project_previews.json` contains valid JSON with an invalid top-level shape; `get`, `register`, and `stop` no longer mask or overwrite that data. Regression coverage asserts the original file is preserved.
- Terminal-run history now also rejects an invalid top-level JSON shape rather than returning an empty history; its regression test asserts the file remains unchanged. The terminal remains disabled because no genuine OS sandbox is verified.
- Web fetch sets HTTPX `trust_env=False`, sanitizes returned hyperlinks (HTTP(S)-only, credential/obvious-local-target filtering, deduplication, fragment removal, secret-query redaction), and persists binary artifacts only for successful HTTP responses. A custom connect-time transport re-resolves hostnames, rejects any non-global answer, and connects to a validated public IP while retaining the original URL hostname for Host/TLS handling. Regression tests cover rebinding and IP pinning, but they remain unrun in the current worktree; this private-httpcore-hook implementation needs isolated runtime verification before the web-fetch feature is treated as production-ready.
- Latest read-only audit: **899 files inventoried, 0 active integration findings** at the time of that audit. Completion remains blocked by fresh full behavioral/build/lint verification and the missing per-run sandbox integration for generated-project terminal execution. Repository AST scan parsed 307 Python files (two access-denied paths excluded); 26 JSON files parsed; `git diff --check` passed. Six directly changed Python files passed AST parsing.
- Docker CLI is not installed. Windows Sandbox did boot and run selected backend tests plus frontend build/lint in earlier isolated runs; firmware-flag output alone was inconclusive. The project terminal remains disabled because ProjectTerminalService lacks its own per-run Windows Sandbox provider/verifier. No BIOS/Windows setting changes were made. A fresh full backend rerun, Vitest, and generated-app execution remain pending.

- Follow-up preview hardening: persisted preview records are now validated on every read/update, including project/version shape, loopback URL and explicit port, status, and timestamp. A tampered external URL is rejected and the original index remains unchanged; AST and whitespace checks passed, but the regression test has not run.
- Added a terminal safety regression that forces the feature flag on while sandbox verification remains false and replaces `subprocess.run` with a fail-fast stub; it asserts the execution guard returns before any subprocess call. AST parsing passed, but the test remains unrun until genuine isolation is available.


## Verification reconciliation — 2026-10-19 evening

- The latest recorded isolated backend run completed with **355 passed, 1 failed**. The remaining failure was the nested provider-startup subprocess timing out after 60 seconds in that copied workspace. The test has since been refactored to exercise registration directly in-process and now includes a malformed optional-provider configuration regression; the revised test is syntax-checked but not yet behaviorally verified.
- The isolated desktop run's **build passed** and **lint passed with 0 warnings/errors**. Its Vitest phase did not run successfully because the earlier command used an unsupported `--minWorkers` flag. The harness was corrected and a separate dependency tree was installed from the lockfile, but the corrected Vitest run has not produced a fresh result log.
- Current worktree checks after the provider-test refactor: Python byte-compilation for the changed test passed and git diff --check passed (only existing LF-to-CRLF notices). No new sandbox was launched because host free RAM was approximately 1.1 GiB and previous sandbox launches caused significant memory pressure.
- Therefore completion is **not yet verified**. Next: wait for adequate host memory, verify no sandbox guest remains, rerun the provider-startup test in isolation, then rerun backend tests and desktop Vitest/build/lint using the corrected offline-capable harness. Keep terminal execution disabled and preserve all existing worktree changes.


## 2026-10-19 essentials follow-up

- Provider startup registration was extracted into a small function so configuration can be verified without launching a nested Python process or importing the entire FastAPI app twice. Existing opt-in flags and required keys/model-path checks are preserved.
- The core state contract now checks the types of `current_stage`, `last_completed_stage`, `intent`, and `selected_capability`, rather than only checking that keys exist and `status` is recognized.
- Latest read-only audit: 902 files inventoried, zero active integration findings, but `completion_ready=false` because fresh isolated behavioral/build/lint verification and the project's own OS-sandboxed terminal remain incomplete. Static verification is not a substitute for those gates.


### Additional work in the current continuation

- Added persistent artifact relationships with self-link, missing-target, archived-artifact, duplicate-link, invalid-relation, and maximum-link checks. Deleting an artifact removes inbound references so the index does not retain dangling edges.
- Added `POST /artifacts/{artifact_id}/links`, `GET /artifacts/{artifact_id}/links`, and `DELETE /artifacts/{artifact_id}/links`. Link responses expose only safe artifact metadata, not local filesystem paths.
- Connected artifact relationships to Unified Search results, so matching transcripts/reports can show their related audio, summaries, and source artifacts without copying linked content into the result.
- Added desktop controls to create and remove artifact links directly from artifact details.
- Corrected durable task completion so repeating a completion update is idempotent while completed tasks still cannot be reopened.
- Goal readiness now blocks duplicate execution when a linked workflow is already active.
- Added a route-parameter regression test suite and GitHub Actions workflow. Current CI results must be checked against the latest branch commit; the full suite has recently narrowed to a small number of remaining failures, and no blanket “all features complete” claim is made.
