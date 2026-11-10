# Lumira Phase D Completion Matrix

This ledger tracks system-level work separately from the Phase A/B/C
requirements. A row is complete only when implementation, integration, and
relevant acceptance evidence exist.

| Requirement | Status | Evidence / blocker |
|---|---|---|
| Data export and restore integrity | VERIFIED | `DataBackupService` exports bounded JSON/JSONL stores with a checksum manifest and validates ZIP entries, paths, symlinks, per-file sizes, checksums and totals before staging verified restore files for per-file atomic replacement. `GET /data/backup` and `POST /data/restore` are registered. Fresh backup service/route tests: **10 passed**. |
| Desktop application completeness | VERIFIED | Desktop API/UI surfaces, including backup/restore controls, pass the complete desktop suite (**40 passed**); packaged installation and restart acceptance remain external. |
| Windows lifecycle and packaging | IN PROGRESS | Fresh NSIS installer built (215,037,910 bytes; SHA-256 `79F33EA28566D61EB7B705307748495F7CC7F644DA383E86243A4102BE3AF323`), silently installed to an isolated per-user test directory, packaged Electron UI returned HTTP 200, bundled Python backend started from the installed runtime and `/health` returned `ok`; core UI/API routes returned HTTP 200. Clean app shutdown and relaunch restored UI/API health. Existing user data was backed up and isolated from the acceptance run. Upgrade from a prior version, uninstall/data-retention journey, and code signing remain unverified. |
| Personal assistant integrations | VERIFIED | Reminder, task, notification, and workflow bridges pass focused repository integration tests (**81 passed**); external calendar/device acceptance remains open. |
| Creation and development studios | VERIFIED | Creator OS, development workflow, artifact generation, and recovery tests pass in the focused repository batch (**81 passed**); untrusted execution remains isolation-blocked. |
| Research and intelligence interface | VERIFIED | Research, memory, project, and artifact bridges pass the focused repository batch (**81 passed**); live provider acceptance remains blocked by resources/credentials. |
| Security and privacy | IN PROGRESS | Authorization, path validation, secret redaction, and resource guards are covered; OS-level untrusted-code isolation is not implemented. |
| Reliability and performance | VERIFIED | Persistence integrity, recovery, resource guards, diagnostics, failure-boundary tests, and packaged-runtime legacy migration/upgrade preservation tests pass; live-provider acceptance remains open. |
| Final end-to-end integration | VERIFIED | Brain, workflow, research, artifact, recovery, backup, and desktop bridge journeys pass repository-focused integration tests; full hardware, provider, packaging, and isolation acceptance remains open. |

Phase D is not claimed complete. The current implementation evidence is
repository-level and does not substitute for external acceptance.

## Verified-row calculation

There are **7/9 verified rows (78%)**. The target of 90% is not reached:
Windows packaging, physical hardware journeys, external image-generation/speech/research providers, and OS-level isolation remain external or unavailable acceptance dependencies.

## Direct Desktop Commander update — 2026-11-10

- Added `SecurityAuditLogService` with atomic persistence, sequence numbers, a SHA-256 hash chain, sensitive-detail filtering, bounded event size/count, and integrity verification. The hash chain is tamper-evident for accidental/partial modification; it is not represented as a cryptographically immutable log against an attacker who can rewrite the entire file.
- Added `/security/audit/integrity` and `/security/audit/events` read endpoints. The preflight endpoint now records only the decision and finding rule IDs; it does not persist the raw user instruction.
- Connected Main Brain's explicit side-effecting capability coordinator to unsafe-operation preflight and security audit recording. If the audit cannot be written, the operation is blocked before capability dispatch.
- Focused security/registry suite: **19 passed**. Brain execution route, pipeline safety, and autonomy permission suite: **17 passed**. Python compilation and `git diff --check` passed in the 19-test batch.
- Phase D security/privacy remains `IN PROGRESS`; this work does not prove genuine OS-level sandbox isolation or a complete external-action approval matrix. The Phase D aggregate remains **7/9 verified rows (78%)** until those acceptance gates pass.
- Desktop validation after separating the CommonJS Node test from Vitest: **40/40 Vitest tests passed across 6 files**; the Node runtime suite passed **2/2** using `npm run test:runtime`; TypeScript/Vite production build passed; Oxlint reported **0 warnings and 0 errors**. The packaged NSIS installer and install/upgrade/restart journey were not run.


## Direct Desktop Commander full-suite checkpoint ? 2026-11-10

- Full backend repository suite: **840 passed, 1 skipped, 0 failed** in
  **452.53 seconds**. The wake-word shutdown timing issue found in the first
  run was corrected and the complete suite then passed.
- Wake-word listener regression suite: **6 passed**. Central tool-selection
  and agent command integration suite: **39 passed**. Focused Phase D data,
  notifications, and related checks: **21 passed**.
- Security/privacy remains **IN PROGRESS**. A passing repository suite does
  not establish Windows OS-level sandbox isolation, immutable audit storage,
  or a complete approval matrix for consequential external actions.
- Phase D remains **7/9 verified rows (78%)**; Windows packaging and the
  security/isolation row remain open pending their specific acceptance gates.


## 2026-11-10 — Sandbox boundary hardening continuation

- Confirmed the host Windows Sandbox runtime can launch a disposable guest and execute a harmless smoke command. The output was written from the guest account `WDAGUtilityAccount`; this proves basic guest boot/command execution only, not Lumira project-terminal integration or complete isolation acceptance.
- Hardened `ContainerSandboxProvider` invocations with a non-root numeric user (`65534:65534`), disabled IPC, PID/memory/CPU limits, `no-new-privileges`, bounded file/process ulimits, a read-only project mount, a read-only root filesystem, no network, dropped Linux capabilities, and a restricted writable `/tmp` tmpfs.
- Added regression assertions for the additional isolation controls. Focused sandbox/terminal gate tests: **8 passed**. `git diff --check`: passed; only pre-existing LF-to-CRLF notices were emitted.
- Full backend baseline remains **840 passed, 1 skipped, 0 failed**; desktop **40/40 Vitest**, **2/2 Node runtime**, production build and lint passed in the earlier verification batch.
- Current host free RAM at the start of this continuation was approximately **1.15 GB / 7.70 GB**. No additional full-suite run, Docker execution, or second Windows Sandbox launch was attempted under this memory pressure.
- The actual project terminal remains fail-closed by default. The Windows Sandbox smoke test is not yet wired into `ProjectTerminalService`; Docker availability and an image containing the required project test tools are also not confirmed. Do not mark OS isolation or Phase D security complete from this work.
- Existing uncommitted files and runtime data were preserved. No reset, cleanup, commit, push, package installation, or user-data deletion was performed.


- Follow-up hardening: `ContainerSandboxProvider.status()` now verifies that the configured default image is present locally after confirming the Docker daemon. A running daemon without the required image returns `sandbox_image_unavailable` instead of a false `verified` status. Added a missing-image regression test; the sandbox/terminal focused suite now passes **9/9** and `git diff --check` passes.


- Environment recheck: Docker CLI is **not installed**; `WindowsSandbox.exe` is present. The earlier one-off Windows Sandbox smoke result confirms the guest can boot and execute a basic command, but no reusable Lumira provider is connected to it. Current free RAM after focused verification: approximately **1.36 GB / 7.70 GB**. Project terminal remains disabled by default.


## 2026-11-10 — Continued cross-phase verification

- Desktop UI: fresh Vitest run **40/40 passed** across 6 files (single-worker cap). Electron backend-runtime tests **2/2 passed**. Oxlint **0 warnings / 0 errors**. TypeScript + Vite production build passed; generated bundle: 448.53 kB JS (118.05 kB gzip), 36.33 kB CSS (8.68 kB gzip).
- Backend cross-phase regression batch: **81 passed** across Phase A pipeline/validation/memory, Phase B voice/artifact/sandbox, Phase C autonomy/agent collaboration, and Phase D backup/security tests.
- Voice idempotency follow-up: **7 passed** across idempotency, recovery, and pipeline tests. The pipeline now fails closed before retranscription if the production memory lookup fails, preventing a duplicate write when it cannot establish whether the audio artifact was already processed. Lightweight injected test adapters without `get_all()` remain supported.
- Python compilation and whitespace checks were run after the source edits; no compile or diff-check failure was observed.
- Fresh capability inventory: **37/99 VERIFIED (37.37%)**, 19 TESTED, 16 IN_PROGRESS, 1 NOT_STARTED, 26 BLOCKED. Do not infer phase completion from the green tests; hardware, live-provider, OS-isolation, and packaging gates remain.
- Fresh terminal sandbox status: `docker_not_installed`; Docker CLI not found. `ProjectTerminalService` remains fail-closed unless an explicit provider passes its availability check. The prior Windows Sandbox guest smoke test does not supply the missing per-run terminal integration.
- Host memory at the end of verification: approximately **1.63 GiB free / 7.70 GiB total**. No full backend suite, live model inference, microphone/speaker acceptance, installer build, or generated-project execution was attempted in this constrained session.
- Phase aggregate status remains A **11/12 (92%)**, B **6/10 (60%)**, C **9/10 (90%)**, D **7/9 (78%)**. No phase is certified 100%; external acceptance gates remain open.


## 2026-11-10 — Backup restore and summary retry hardening

- Phase D backup restore now rejects duplicate ZIP entries, duplicate manifest paths, unlisted archive payloads, symbolic links, encrypted entries, invalid checksum metadata, declared-size mismatches, total-size mismatches, symlinked restore targets, and target directories that resolve outside the configured data root. Export skips symlinked source files.
- Added adversarial backup tests for unlisted payloads, duplicate manifest paths, total-size mismatch, and symlink export leakage. Backup service + route suite: **10 passed**.
- Phase B summary retries now reuse a prior active summary for the same transcript only after SHA-256 integrity verification. Corrupt or missing existing summaries fail closed rather than generating duplicate replacements.
- Added replay and corruption tests for summary idempotency. Combined fresh focused acceptance across summary provider/resource handling, voice retry linkage/idempotency, and backup service/routes: **18 passed**.
- These changes improve retry safety and backup trust boundaries; they do not close the external live-provider, microphone/speaker, Windows packaging, or OS-isolation gates. Phase aggregates and Phase Zero inventory remain unchanged pending their full acceptance criteria.


## 2026-11-10 — Final verification and backup hardening

- Fresh full backend repository suite: **866 passed, 1 skipped, 0 failed** in **339.23 seconds**; one expected Pydantic serializer warning remains in the deliberate mutable-state-corruption test. `pip check`: no broken requirements.
- Backup restore hardening rejects duplicate ZIP entries, duplicate manifest paths, unlisted payloads, symbolic links, encrypted entries, drive/stream-qualified paths, oversized manifests, invalid scalar types, declared-size/checksum mismatches and total-size mismatches. Export excludes symlinked files. Backup service/route tests: **10 passed**.
- Project terminal is now explicitly hard-disabled by default (`OS_SANDBOX_ENABLED = False`) until a reusable OS-level isolation provider is integrated and independently verified. The stale capability test was updated to match this fail-closed default. Terminal/sandbox/backup/provider focused regression batch: **61 passed**.
- Desktop acceptance rerun: **40/40 Vitest**, **2/2 Node runtime**, Oxlint **0 warnings / 0 errors**, TypeScript/Vite production build passed. The packaged NSIS installer and install/upgrade/restart journey remain unrun.
- Live local Qwen chat and summary service, Moondream image analysis with saved report artifact, and the local Faster-Whisper + Ollama voice idea pipeline were exercised. These improve A/B evidence but do not close physical hardware, packaging, external-provider or OS-isolation gates.
- Phase D remains **7/9 verified (78%)**. Security/privacy remains `IN PROGRESS`; Windows lifecycle/packaging remains `BLOCKED`.


## 2026-11-10 — Recovered full-suite result

- The interrupted full backend run completed successfully: **873 passed, 1 skipped, 0 failed** in **904.16s**. `pip check` passed; `git diff --check` exited 0 with only line-ending notices.
- Follow-up transcript retry implementation was separately verified by **12 voice/transcript retry tests** and a **25-test provider/artifact regression batch**; Python compileall passed.
- No Phase D status promotion: Windows upgrade/uninstall/signing and genuine OS-level isolation remain open. ProjectTerminalService remains disabled by default. Phase D remains **7/9 verified (78%)**.

## 2026-11-10 ? Windows Sandbox provider implementation and live guest verification

- Added `WindowsSandboxProvider` with a disposable `.wsb` guest, disabled guest networking/clipboard/audio/video/printer/vGPU, protected-client mode, read-only control/runtime mappings, a bounded writable project snapshot, and a nonce-correlated result channel.
- Project snapshots reject symlinks/reparse points and non-regular files, cap the tree at 5,000 files / 250 MiB, and exclude `.git`, virtual environments, caches, `.env*`, credential JSON, and key/certificate material. The temporary host staging tree grants access only to the current interactive identity.
- The guest applies a Windows Job Object before starting the allowlisted command: 64-process limit, 768 MiB per-process memory, 1 GiB job memory, kill-on-job-close, and a 50% CPU hard cap. Result validation now rejects any guest result that does not explicitly attest these limits.
- Live acceptance on the host: `WindowsSandboxProvider.status()` returned available; a fresh isolated guest executed a generated one-test pytest project as `WDAGUtilityAccount`; result was **1 passed in 0.18s**, exit code 0. The provider returned success only after validating the nonce, guest identity, and `job_limits_applied=true`, and confirming VM shutdown. The staging directory was removed and no Windows Sandbox VM/session process remained after completion.
- Focused regression after tightening result validation: **33 passed** across Windows Sandbox, Docker sandbox, terminal feature-gate, and project-capability tests. Python compilation passed. `git diff --check` exited 0; Git emitted only LF-to-CRLF working-copy notices.
- This is a verified provider-level live test, not yet the complete Lumira terminal integration. `ProjectTerminalService` remains hard-disabled by default and does not select this provider automatically; the feature activation/readiness path still needs to be wired to the platform-specific provider and tested end-to-end. Do not promote the Phase D security/isolation row or Phase C OS-isolated execution criterion yet.
- Host memory after guest shutdown: approximately **2.39 GiB free / 7.70 GiB total**. No original project or user data was modified by this smoke test.
