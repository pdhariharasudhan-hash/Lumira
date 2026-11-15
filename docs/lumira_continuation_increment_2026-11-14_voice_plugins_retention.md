# Lumira continuation increment — 2026-11-14 (voice, plugins, retention, integrity)

## Implemented in this increment

### Voice recording retention
- Added `VoiceRetentionService` with a bounded, read-only preview of expired audio recordings, using the consent receipt and recorded retention expiry as the decision source.
- Audio marked `until_deleted` is retained. Missing or malformed consent/retention metadata is classified as unknown and is not automatically deleted.
- Added `GET /voice/retention/preview` and `POST /voice/retention/expire`. Deletion requires a strict boolean owner confirmation in the request.
- Expiry writes a durable preflight audit event before deleting each recording. It preserves transcripts and summaries, removes the audio artifact, and then removes the audio ID from cognitive experience links.
- Corrected expiry result accounting so an audio file that was deleted but later failed memory cleanup or completion auditing is still reported as deleted with a side-effect warning.

### Memory lifecycle
- Added atomic `MemoryService.remove_artifact_references()` for cognitive experience artifact links.
- Added `POST /memory/retention/preview`. The owner supplies retention days by collection; the service reports eligible, retained, protected and unknown records. This route is preview-only and performs no deletion.
- Existing verified learning and active goals remain protected by the retention planner.

### Plugin lifecycle API
- Added `/plugins` routes for listing manifests, approved capability discovery, manifest registration, permission approval, permission revocation and disabling.
- Every mutation requires the explicit confirmation field where approval/revocation/disable is involved and records preflight/completion audit events.
- The plugin registry remains metadata-only: no package installation, dynamic import, or third-party code execution is enabled by these endpoints.
- Changed plugin registry first-run initialization to use atomic `read_or_create()`.

### Artifact integrity and reconciliation
- Added explicit owner-confirmed `POST /artifacts/consistency/repair` to reconcile only the derived memory mirror from the canonical artifact index.
- The repair route requires durable preflight audit, records completion/partial outcomes, and reports possible side effects if completion auditing fails.
- Canonical duplicate artifact IDs remain fail-closed.

### Device capability authorization
- Added namespace-to-permission mapping for robot, camera, microphone/audio, smart-home, vehicle and file actions. A capability alias such as `robot.move` now requires the explicit `robot.motion` permission instead of bypassing the sensitive permission check.

## Static checks and constraints
- No tests, test suites, benchmarks, live provider calls, sandbox runs, or hardware commands were executed in this increment.
- `python -m compileall -q app` completed successfully after the code changes.
- `git diff --check` completed successfully; Git emitted only LF-to-CRLF normalization notices.
- Existing runtime data was not reset or deleted. No files were staged, committed, pushed, or force-rewritten.
- The master requirement ledger remains 914 records: 64 IMPLEMENTED, 821 IN_PROGRESS, 27 BLOCKED, 1 NOT_STARTED and 1 VERIFIED at the last recorded reconciliation. This increment does not justify claiming 50% or 100% overall completion.
- Windows Sandbox execution remains disabled until actual per-run isolation is independently accepted. Plugin execution is not enabled; this is a permissioned metadata lifecycle, not a safe arbitrary-code runtime.


## Additional plugin runtime and host-concurrency build
- Added `PluginRuntimeService`: trusted application code can register async handlers for an approved plugin capability. Each invocation rechecks current plugin approval and declared/granted permissions, then passes through the existing schema validator, one-time approval system, execution budget and durable security audit. Plugin packages are never dynamically imported or executed.
- Wired a per-app plugin runtime into FastAPI lifespan. A corrupt/unavailable plugin registry degrades only the plugin subsystem; the core Lumira app remains available and plugin runtime routes return service-unavailable.
- Added runtime handler discovery, session-bound one-time approval and capability execution endpoints. Both approval and execution require an existing Lumira session; high-risk tool calls retain exact session/tool/argument-bound one-time approval.
- Added a process-wide single-slot tool execution gate. Concurrent tool calls are deferred rather than competing for limited local RAM; the lock is released on success, failure, timeout and cancellation.
- Extended device permission mapping to distinguish audio output from microphone input.
- Memory retention reports are now bounded to 500 records per result category with explicit truncation indicators, while preserving total counts.
- Static validation after these additions: `python -m compileall -q app` and `git diff --check` are the only validation operations planned; no tests are to be run.

- Final static pass after the plugin runtime API, session binding, resource gate and retention-output bounding: `python -m compileall -q app` passed and `git diff --check` passed (LF/CRLF notices only). No test command was invoked.

- Final post-edit static compile and diff check after the latest plugin-runtime failure mapping: `python -m compileall -q app` and `git diff --check` passed. Git reports 0 staged files; no tests were run.
