# Lumira core infrastructure increment — 2026-11-14

## Durable event bus
- Added `EventBusService` with bounded JSON-safe event payloads, stable event IDs, atomic persistence, event-name/source validation, redaction of sensitive payload values, event listing/cursor pagination, and process-local synchronous subscribers scoped to the event-store path.
- Async subscriber callbacks are rejected at registration; durable asynchronous consumers should use the message queue rather than silently dropping coroutine work.
- Hardened `CoreEventLogService`: replaced silent JSON-corruption fallback and direct writes with atomic storage, strict schema/identity validation, bounded event data, sensitive-value redaction, and explicit storage failure responses. Preserved the public record/search/recent response shapes and the historical `event-` ID prefix.

## Durable message queue
- Added `MessageQueueService` with bounded messages, deduplication keys, atomic claims, expiring worker leases, bounded retries, retry delays, dead-letter state, acknowledgement, and redacted message payload/error storage.
- Added management APIs for enqueue, list, claim and acknowledge. Mutating operations write preflight and completion audit events.
- Queue operations do not execute arbitrary code. A registered consumer/worker must claim, process and acknowledge messages.

## One-shot task scheduler
- Added `TaskSchedulerService` with timezone-aware one-shot schedules, explicit owner approval, atomic due-job claims, expiring claims and recovery, completion, cancellation, and bounded storage.
- Added APIs for scheduling, listing, claiming due work, finishing and explicitly confirmed cancellation. Mutations are audited before and after the state change.
- The scheduler deliberately does not launch unattended arbitrary commands. A managed dispatcher and policy-bound worker remain outstanding.

## Integration and traceability
- Registered the core runtime API router exactly once and added event bus, message queue and scheduler health probes to system health.
- Updated master requirement traceability for `PROMPT-04-12`, `PROMPT-04-13`, and `PROMPT-04-14`. Their statuses remain IN_PROGRESS because asynchronous event delivery, queue worker integrations and managed scheduled-task dispatch are not complete.
- The ledger remains 914 records with status counts: 64 IMPLEMENTED, 821 IN_PROGRESS, 27 BLOCKED, 1 NOT_STARTED and 1 VERIFIED.

## Validation and limits
- No tests, test suites, benchmarks, provider calls, sandbox executions or hardware commands were run.
- Static validation only: `python -m compileall -q app`, targeted AST parsing of the seven changed core files, and `git diff --check` passed.
- No runtime data was reset or deleted. No files were staged, committed or pushed.
- This increment is not evidence of 50% or 100% overall Lumira completion.


## Scheduled dispatch handoff
- Added `ScheduledTaskDispatchService` to connect due one-shot schedules to the durable background-agent task queue. Dispatch requires an explicit owner-confirmed API request and a current `agent.dispatch` autonomy grant; it does not bypass the Brain verification gate in the agent worker.
- Added schedule-scoped idempotency keys to `BackgroundAgentTaskService.create()`. Repeated dispatch attempts return the existing background task rather than creating duplicates.
- Added scheduler state `dispatched`, background-task linkage, and a result synchronizer that maps completed/failed/interrupted background task states back to the schedule record.
- Added `POST /core/schedule/dispatch-due` and `POST /core/schedule/sync-results`. Dispatch queues work for the existing agent worker; it does not execute arbitrary tasks inline and no unattended scheduler loop is enabled.
- Static compile, targeted AST parsing of nine changed core files and `git diff --check` passed after these changes. No tests were run.

## Background task lifecycle and memory cleanup hardening ? 2026-11-14
- Fixed startup recovery so constructing a BackgroundAgentTaskService no longer changes durable work. Queued jobs remain queued; only running jobs are marked interrupted during explicit application-startup recovery.
- Added explicit owner-confirmed retry for failed/interrupted jobs with a three-retry ceiling and a fresh autonomy-permission check for autonomous work.
- Added explicit cancellation for queued jobs. Task capacity now evicts only terminal records and refuses insertion if every stored task is active, rather than silently deleting queued/running work.
- Added optional API idempotency keys, duplicate-safe dispatch, retry and cancel endpoints, and a cancelled status filter.
- Added MemoryService.remove_artifact_references() to remove expired audio references from cognitive experiences and mark matching legacy artifact-index records deleted. Voice retention cleanup can now invoke the memory cleanup operation instead of leaving dangling references.
- Application lifespan performs abandoned-running-task recovery once at startup. This is not a background scheduler or a recurring autonomous loop.
- Static Python compilation and git diff --check passed. No tests were run.

## Device command boundary hardening ? 2026-11-14
- Tightened the local HTTP device transport to reject link-local, reserved and special-use IP ranges in addition to requiring literal private/loopback IP addresses. This blocks metadata/link-local targets and DNS-based endpoint ambiguity.
- Bounded connect/read timeout configuration to 0.1?10 seconds.
- Device command authorization now fails closed when a stored permission or capability record is not a list of strings.
- Expanded capability-to-permission mapping for file operations and shell/process/terminal/system command namespaces. Unknown file operations require the stronger files.write permission.
- Device ecosystem readiness planning now uses the same permission mapping as the command gateway, avoiding conflicting eligibility decisions.
- Physical discovery and hardware execution remain dependent on a configured trusted transport and explicitly registered devices. No hardware commands were sent.

## Operational health integration ? 2026-11-14
- System health now reports durable background-task storage, active agent execution leases, and the live RAM/resource profile alongside the event bus, queue and scheduler.
- Health probes are read-only and bounded; provider registration is still not represented as proof of remote reachability.

## Privacy and scheduled-worker integration ? 2026-11-14
- Scheduled task descriptions and metadata, and background-agent task descriptions, are now redacted before durable storage to avoid persisting API keys, passwords, bearer tokens and similar secrets embedded in task text or metadata.
- Scheduled jobs dispatched through the API now run through the RAM-aware background worker and automatically synchronize their final background-task outcome into the schedule record with preflight/completion audit events.
- Updated source traceability for PROMPT-04-14 and PROMPT-04-15; both remain IN_PROGRESS pending operational acceptance and broader worker recovery/dispatcher coverage.

## Owner-controlled queued-task recovery ? 2026-11-14
- Added `POST /background-tasks/dispatch-queued` to resume durable queued jobs after a restart or resource-pressure deferral.
- Recovery requires explicit owner confirmation, is bounded to five tasks per request, writes preflight/completion audit events, and routes each task through the RAM-aware worker lease.
- If the host is still under pressure, the worker leaves the task queued; this endpoint does not bypass autonomy permission or Brain verification.

## Memory cleanup and audio capability alignment ? 2026-11-14
- Voice-retention cleanup now removes deleted audio records from the legacy artifact mirror as well as unlinking artifact IDs from cognitive experiences; this avoids leaving tombstoned IDs that could still appear in broad memory queries.
- Device permission mapping now distinguishes audio playback/speech synthesis from microphone capture/transcription and fails toward the capture permission for unknown audio operations.

## Queue claim ownership ? 2026-11-14
- Message queue claims now issue cryptographically random lease tokens. Acknowledgements require the matching token and use constant-time comparison, preventing another local caller from completing or failing a message it did not claim.
- Expired and legacy running leases are recovered back to queued/dead-letter state with the token cleared. Queue records remain bounded and all state changes remain atomic.

- Queue list responses now omit worker lease tokens. The token is disclosed only in the atomic claim response and is required for acknowledgement.

## Capability router consolidation ? 2026-11-14
- Expanded deterministic feature gating across planning, goals, agents, workflows, recovery, projects, code generation, artifacts, memory, unified search, research, image generation, observability and voice capabilities. Feature state and provider readiness are checked before dispatch.
- Capability names are now normalized and validated before mode resolution, preventing malformed/non-string names from raising or bypassing normalized mode checks.
- Payloads must be JSON-safe and are bounded to 64 KB; known text fields have a 10,000-character ceiling. Missing payload remains an empty object, while malformed non-object payloads are rejected rather than silently coerced.

## Feature catalog expansion ? 2026-11-14
- Added explicit feature domains for growth/business planning, operations, creator workflows, technical generation, assistant, personal organization, scheduling, and provider-gated video generation.
- Extended the capability-to-feature matrix so supported capabilities are blocked when their feature is not activated, dependencies are unavailable, or required providers are missing.
- Feature records were added without enabling them or changing existing feature state. Dependencies and provider readiness remain the activation gate.
- Updated traceability for AREA-26 and PROMPT-04-06; both remain IN_PROGRESS.

- Added explicit capability-router operations for dependency planning and atomic dependency-bridge activation, alongside direct single-feature activation. Feature IDs are included in the same bounded input validation.

## Multi-model orchestration safety ? 2026-11-14
- Reworked the multi-model orchestrator to authorize every provider through the persisted local/cloud access policy before invoking it. Unknown provider scopes default to external and require explicit cloud consent.
- Integrated RAM-aware fan-out caps: constrained/unknown hosts use a maximum of two candidates (one when resource telemetry is unavailable), local providers run sequentially, and normal hosts cap parallel candidate calls at four.
- Prompt, context and model output are bounded; sensitive values are redacted from prompts, context, outputs and provider metadata before they are passed through or returned.
- Model provider failures and policy denials are isolated per candidate; no untrusted provider exception text is exposed.

## Persistent model health and circuit breaker ? 2026-11-14
- Added a bounded atomic model-health ledger with success/failure counts, rolling average latency, last outcome and a circuit breaker after three consecutive provider failures.
- Multi-model selection skips models with open circuits and exposes health in model listings. Provider policy denials do not count as provider failures.
- Added a read-only GET /multi-model/health status endpoint. Circuit reset requires explicit owner confirmation at the service boundary.

- Added the persistent model-health circuit-breaker state to system health reporting, including tracked model count and currently open circuits.
- Updated traceability for CAT-system-02.capability-01 and PROMPT-05-19; both remain IN_PROGRESS.

- Added an owner-confirmed, preflight/completion-audited model circuit reset endpoint. The automatic cooldown remains the default recovery path; manual reset is an explicit owner action.

## Background task audit completion ? 2026-11-14
- Added preflight and completion security-audit records for background task creation, retry, cancellation and queued-task dispatch. If the audit store is unavailable, new state changes are blocked; post-mutation audit failures are reported with possible-side-effect metadata.
- Startup recovery now returns its recovered-task count, and capacity management recognizes cancelled tasks as safely evictable terminal records.

## Tamil / English / mixed intent recognition ? 2026-11-14
- Reworked deterministic intent classification to recognize bounded Tamil-script phrases, romanized Tamil phrases, English command prefixes and parser-derived capability intents.
- Added a backward-compatible detailed classifier result with detected language, confidence and classification source. Existing callers of \`classify()\` still receive the original intent string.
- Updated traceability for SRC42-PART-13-012 and SRC42-PART-39-004; both remain IN_PROGRESS pending voice and language acceptance.

## Language API surface ? 2026-11-14
- Registered \`/language/capabilities\`, \`/language/detect\`, \`/language/detect-many\`, \`/language/classify\` and \`/language/classify-many\` APIs for bounded Tamil, English, romanized Tamil and mixed-language input.
- Documented that transliteration recognition is lexicon-based and lower-confidence than native Tamil script; no claim of general-purpose translation was added.

## Feature lifecycle audit boundary ? 2026-11-14
- Feature activation, dependency-bridge activation and deactivation now write preflight and completion/blocked security audit records. Mutations are blocked when preflight audit storage is unavailable; post-mutation audit failures report possible side effects.
- Updated traceability for AREA-26 and PROMPT-04-06; both remain IN_PROGRESS.

## Configured chat model startup integration ? 2026-11-14
- Added an adapter that exposes existing local Ollama and OpenAI-compatible chat providers through the multi-model registry interface.
- Application startup registers only providers whose explicit feature flags are enabled. Cloud registration additionally requires a configured model and API key; provider access still passes through the persisted AI-mode/cloud-consent policy before every request.
- Startup performs no provider network calls. Local Ollama has higher selection priority; the cloud model is a fallback candidate only when configured and permitted. Registration failures are isolated and do not expose exception details or credentials.
- Configuration flags: \`LUMIRA_OLLAMA_CHAT_ENABLED\` and \`LUMIRA_CLOUD_CHAT_ENABLED\`; local model settings use \`LUMIRA_OLLAMA_BASE_URL\` and \`LUMIRA_OLLAMA_CHAT_MODEL\`; cloud settings use \`LUMIRA_CLOUD_CHAT_BASE_URL\`, \`LUMIRA_CLOUD_CHAT_MODEL\`, and \`LUMIRA_CLOUD_CHAT_API_KEY\`.
- Updated traceability for CAT-system-02.capability-01 and PROMPT-05-19; both remain IN_PROGRESS.

- Integrated the multi-model orchestrator into the normal Brain conversation provider route. When configured models exist, ordinary chat now uses the same RAM-aware selection, model health and provider consent gates instead of bypassing the orchestration layer. Failed orchestration is returned directly rather than triggering a second provider call.

## Voice capture quality and retention consistency ? 2026-11-14
- WAV recordings now receive bounded local audio-quality diagnostics (level, silence, clipping and format) before storage; analysis retains no audio samples and does not send audio to a provider.
- Explicit retention cleanup now removes durable memory references before deleting the audio binary. If memory cleanup fails, deletion is skipped so the artifact remains available for retry; if deletion fails after unlinking, the remaining artifact is reported with the reference-cleanup outcome.

## Fixed-interval recurring schedules ? 2026-11-14
- Added owner-approved recurring schedules at \`POST /core/schedule/interval\` with bounded intervals (1 minute to 1 year) and bounded run counts (1 to 1000).
- Occurrence count increments atomically when a due job is claimed. Successful completion re-arms the next occurrence; missed intervals are skipped rather than dispatched in a burst. Failed occurrences stop the series.
- Every occurrence still uses the explicit owner-confirmed dispatch endpoint, current autonomy permission, idempotent background-task creation and RAM-aware worker. No unattended scheduler loop or hidden execution was enabled.

- Corrected recurring dispatch idempotency to use a unique schedule-occurrence key rather than a schedule-wide key. Each approved occurrence can now create exactly one distinct durable background task, while retries of that same occurrence reuse the existing task.

- Updated the background worker's schedule completion bridge to parse both legacy one-shot idempotency keys and the new per-occurrence recurring keys, so completion re-arms the correct recurring schedule record.
