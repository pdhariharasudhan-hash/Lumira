# Lumira Completion Implementation Plan

> **For agentic workers:** Use this checklist as the persistent execution handoff. Continue in the existing `codex/lumira-full-implementation` worktree; preserve all existing changes and user data.

**Goal:** Complete and verify the approved Lumira capabilities through integrated, persistent, permission-aware workflows.

**Architecture:** Keep the existing FastAPI, service, persistence, and desktop boundaries where sound. Add explicit bridges at service interfaces, keep external provider and OS capabilities opt-in, and fail closed when security or readiness cannot be verified.

**Tech Stack:** Python/FastAPI/Pydantic, pytest, existing JSON/SQLite persistence, Electron/TypeScript/Vite, Windows Sandbox or a verified container runtime.

**Spec:** User-approved G01–G22 backlog and 30-feature Lumira specification; corroborate against `docs/feature_completion_matrix.md` and the current source before each change.

## Global Constraints

- Use the existing implementation worktree and preserve its staged deletions, unstaged edits, untracked files, and all on-disk runtime data.
- Write a regression test, observe the expected failure, implement the narrowest fix, and rerun the relevant tests.
- Do not install dependencies, run live network requests, launch generated code, or enable terminal execution without a verified per-run OS sandbox.
- Do not push, merge, rewrite history, change repository visibility, or delete user data.
- Treat documentation, registries, UI screens, and mocks as evidence of wiring only; verify user-facing behavior at the actual service boundary.
- Keep original `E:\Hari\personal_ai_core` untouched and confirm its Git state after work.

## Review Focus

1. Optional provider SDKs missing at startup — core app must still import; test with imports intentionally blocked.
2. Runtime and private data tracked by Git — ignored for future changes and untracked without deleting local copies.
3. DNS changes, redirects, unusual IP encodings, and private-address targets — rejected before any request reaches a private host.
4. Sandbox misconfiguration, false readiness, or guest failure — no host process execution and terminal stays disabled.
5. Persistence corruption, duplicate workflow retries, and interrupted recovery — preserve source data and return an explicit recoverable error.

## Execution Tasks

### Phase 1 — Security and launch boundaries

- [x] **G01:** Ignore runtime/private data and remove already-tracked runtime outputs from the index while retaining every local copy. Verify representative ignore paths and a zero-missing-file inventory.
- [x] **G02:** Preserve one authenticated app entry point, constrain launch binds to loopback, remove developer-specific launch paths, and verify local auth and optional-provider startup. The provider registration suite remains unverified in this environment because `urllib3` is missing; the import-blocked startup regression passes.
- [ ] **G07:** Route terminal readiness and execution through the platform OS-sandbox provider; prove fail-closed behavior and leave execution disabled until independent host verification.
- [x] **G09:** Validate URL/IP forms, resolve and pin public addresses per connection, revalidate redirects, block private/reserved targets and retries, bound DNS/connect time, and test with fake DNS/transport only.

### Phase 2 — Core state and idea-to-project workflow

- [ ] **G03:** Audit persistence owners and schemas; add versioned, non-destructive migration and corruption-preservation tests. The atomic JSON store avoids absent-read side effects; device profiles and device registry validate additive legacy migration; backup restore refuses overwrite; planner history validates its existing list schema and uses atomic cross-process updates. The focused persistence suite passed 47 tests with one platform skip. Broad schema migration and interrupted multi-file restore recovery remain open.
- [ ] **G04/G15:** Unify Brain/core/provider orchestration through one readiness-aware provider contract; verify missing providers and provider failures.
- [ ] **G05:** Connect conversation, provenance-aware memory extraction, approval policy, persistent retrieval, and user inspection/control.
- [ ] **G06:** Connect idea capture, validation, project creation, task breakdown, reviewed code proposal, artifacts, and learning without enabling unsafe execution.

### Phase 3 — Research, artifacts, voice, and personal organization

- [ ] **G10/G11:** Persist research source citations and artifact relationships; connect research to knowledge, projects, and tasks.
- [ ] **G12:** Connect voice capture, transcription, language identification, summary, artifact storage, search, and playback with provider readiness gates.
- [x] **G13:** Add deterministic English/Tamil/romanized/mixed-language evaluation and report only supported proxy metrics. Semantic fluency and transliteration quality still require native-speaker evaluation.
- [ ] **G14:** Connect goals, milestones, tasks, schedules, notes, learning feedback, progress, and resume state.
- [ ] Features 14–16 and 29: verify artifact manager, unified search, image generation, and knowledge library workflows.

### Phase 4 — Desktop, automation, preview, devices, and extensions

- [ ] **G08/G16:** Implement supervised preview lifecycle and verify desktop install, upgrade, restart, and recovery boundaries.
- [ ] Features 7–10, 18–23: integrate projects, coding proposals, bounded autonomy, workflow automation, recovery, notes, todos, and progress UI.
- [ ] **G17:** Keep device transport opt-in and bounded; test authorization, private endpoint policy, timeouts, and hardware-unavailable behavior.
- [ ] Features 27–30/G18: integrate capability activation, electronics/inventor artifacts, knowledge, and versioned permission-controlled plugins without executing untrusted code.

### Phase 5 — Reproducibility, resource gates, and evidence reconciliation

- [ ] **G19:** Verify checkpoint, failure, resume, post-resume verification, and audit history end to end.
- [ ] **G20:** Make backend and desktop CI checks reproducible from clean dependency state without mutating user data.
- [ ] **G21:** Measure startup, memory, disk, provider, and background-process usage; report only measured values.
- [ ] **G22:** Reconcile status matrices and documentation against fresh test/build evidence and external-provider/hardware gates.
- [ ] Re-run the focused suite per changed subsystem, then the feasible backend/desktop suites; report blocked checks explicitly.

## Dependency Order and Acceptance

1. G01/G02 must precede exposing private data or network services.
2. G07/G09 must stay fail-closed and must precede any terminal or arbitrary URL feature activation.
3. G03 precedes durable memory, artifacts, goals, and recovery connections.
4. G04/G15 precede model-dependent conversation, research, voice, image, and learning integrations.
5. G05/G06/G10–G14 establish source provenance and durable personal workflows.
6. G08/G16–G20 establish safe execution lifecycle, desktop continuity, plugins, and reproducible acceptance.
7. A task is complete only when a relevant automated test failed for the missing behavior before the fix, passes afterward, its connected workflow is exercised where feasible, and the feature matrix reflects the evidence and remaining external gates.

## Current Session Checkpoint

- Existing isolated worktree: `C:\Users\Administrator\AppData\Local\Temp\lumira-full-implementation`.
- Branch/HEAD at resumption: `codex/lumira-full-implementation` / `745be3c5643d09d96ae9227f9e995c5616f886bb`.
- Original `E:\Hari\personal_ai_core` remains on `main` at the same HEAD with a clean status; test runs were isolated from it.
- G01: 284 personal/runtime paths are staged for untracking, every corresponding local file still exists, and the runtime-ignore regression passed.
- G02: launch, local authentication, and import-blocked optional-provider startup checks pass. `test_provider_startup_registration.py` cannot collect here because the installed environment lacks `urllib3`; no dependency was installed.
- G07: platform provider selection is wired and fail-closed tests pass. `OS_SANDBOX_ENABLED` remains false. No Windows Sandbox/container process was launched; filesystem/network/process-limit/cancellation acceptance on a real host remains a blocker.
- G03: cross-process atomic-store, persistence/work-item, backup/restore, profile/registry migration, and planner-history tests pass. Missing-store reads return a copied default without creating directories or lock files. Restore validates archive contents before filesystem writes, rejects existing targets without overwriting them, stages new files, and uses no-clobber hard-link installation. Device profiles and registry preserve legacy fields and persist the v1 marker only on atomic writes. Planner history preserves its legacy list format, validates corruption without rewriting it, and serializes concurrent updates. The focused G03 suite passed 47 tests, 1 skipped. Migration coverage remains partial across persistence owners; interrupted multi-file restore recovery remains open.
- G09: 57 deterministic SSRF and web-access tests pass, including private IPv4/IPv6, redirect rejection, DNS rebinding, malformed authority, actual pinned-fetch path, and a bounded DNS/connect timeout. No live external network was used.
- Language evaluation, plugin metadata/consent registry, and existing project-preview focused tests pass. Plugin code execution is not implemented or enabled; preview lifecycle supervision remains incomplete.
- Latest focused cross-area regression run: 171 passed, 1 skipped. A subsequent focused G03 run passed 46 tests with 1 platform skip, including three planner persistence regressions observed failing before the change. It covers G01/G02, atomic and work-item persistence, data backup/restore, G07 provider selection and terminal gate, G09 web access/SSRF, language evaluation, plugin registry, and project preview. The Git ignore checks needed a process-scoped `safe.directory` override for the temporary worktree; with that environment setting they pass. A later backup/restore rerun after the no-overwrite change passed 16 tests with 1 platform skip. Skips remain platform-gated.
- G03 absent-store test: confirmed red before the implementation change, then passed in the 173-test run. No original repository data was used by this test.
- G03 backup-collision and device-profile schema tests were confirmed red against the previous behavior, then passed after changes. Restore refuses conflicting files before creating any archive targets, so an existing user file and earlier entries from that same restore remain unchanged.
- Pytest required a session-owned `--basetemp` under `%TEMP%` because the default `pytest-of-Administrator` directory is inaccessible to the sandbox user.
- `Get-Process` found no Windows Sandbox, Docker, containerd or Podman process; WMI process inventory was denied. This session launched no sandbox software. G07 terminal remains hard-disabled pending verified per-run OS isolation.


## Resume checkpoint — 2026-11-11

- Continued in the existing worktree and preserved the staged, unstaged, and untracked implementation state. Original checkout was recorded clean on `main` at the shared HEAD when resuming.
- G04: corrected autonomy mapping so persistent `workflow_automation` and `business_operations` capabilities require `workflow.run`; wired runtime feature readiness for `search → unified_search`. This remains a first-slice mapping, not complete generic enforcement.
- G04: changed `LumiraCore.run()` to invoke `BrainService` with `execute_capability=project_generation`, then map its capability result into the established `run()` response fields. Added regression coverage for delegation, legacy response shape, Brain rejection, explicit invalid validation, and incomplete capability success payloads.
- G05: existing changes provide user-controlled correction/forget, source/provenance retention, archived-record filtering, and bounded read-only conversation context. Relevance remains deterministic keyword scoring; do not describe it as semantic retrieval.
- Focused G04/G05 suite **before the latest `LumiraCore.run()` change**: 51 passed. The new `tests/test_core.py` regressions and the changed implementation are pending verification. Terminal execution is prohibited by the current handoff until OS sandbox isolation is verified; `OS_SANDBOX_ENABLED` remains false and no sandbox runtime is available from recorded checks.
- Original checkout: `E:\Hari\personal_ai_core`, `main`, clean at `745be3c5643d09d96ae9227f9e995c5616f886bb` at resume. Implementation remains at `C:\Users\Administrator\AppData\Local\Temp\lumira-full-implementation`, branch `codex/lumira-full-implementation`.

## Resume checkpoint — 2026-11-12

- Preserved the existing staged deletions, unstaged edits, and untracked implementation files. Work remains on `codex/lumira-full-implementation`; no cleanup, reset, or generated-code execution was performed.
- G05 regression: corrected values and archived records remain in persistent audit history, while active retrieval/search omit superseded values and summaries exclude archived records. The first regression run showed the new assertions failing before the implementation. The focused memory, evolution-route, and conversation-routing suite then passed **27 tests**.
- G04: extended the shared runtime feature-readiness gate to both image-generation capability names and all provider-backed research operations. Disabled and not-ready states stop dispatch before provider calls; each gate case was confirmed failing before the mapping.
- Combined G04/G05/provider integration verification passed **90 tests** across core delegation, Brain coordination, capability feature gating, provider-backed conversation, memory lifecycle/evolution, bounded conversation context, image readiness, and research/provider behavior.
- Terminal/generated-code execution remains disabled; this is not a prerequisite for the focused Python unit tests run here. Broader memory approval, project grounding, migration coverage, and complete generic feature readiness enforcement remain open.

### Immediate next steps

1. Continue G04 by tracing remaining `LumiraCore.plan/build/execute/generate` and workflow-step routes; consolidate only where API contracts and Brain gate behavior can be preserved.
2. Trace remaining `LumiraCore.plan/build/execute/generate` and workflow-step calls for bypasses of Brain verification, preserving each established result contract.
3. Start G06's idea-to-project workflow once G04/G05 acceptance gaps are closed; keep terminal execution disabled until OS isolation is independently verified.
4. Keep preview process supervision and hardware/provider features gated on their external prerequisites.
