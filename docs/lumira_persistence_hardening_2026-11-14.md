# Lumira persistence and state-integrity build increment — 2026-11-14

## Implemented in this increment

- Extended `AtomicJsonStore` with `read_or_create()` for one-time, cross-process-safe store initialization and `update(..., write_if_changed=True)` for serialized schema normalization without needless file replacement.
- Hardened `FeatureRegistryService`: catalog initialization/repair now uses the atomic store boundary; extension registration, dependency-batch activation, single-feature activation, deactivation, health updates and extension removal now validate and mutate the same locked snapshot.
- Hardened `MemoryService` startup and read-time schema normalization so v0-to-v1 migration and defaults are applied inside one atomic transaction. Removed the prior split read/migrate/write sequence.
- Hardened `BackgroundAgentTaskService`: task storage now uses `AtomicJsonStore`; task creation, queue claiming, completion, and restart recovery use cross-process transactions; record shapes and list filters are bounded and validated.
- Hardened `NotepadService`: initialization and create/update/delete operations now use atomic transactions.
- Hardened `PersonalTodoService`: initialization and mutations use atomic transactions; persisted task identity, status, priority, progress, timestamps and optional metadata are validated.
- Hardened command and pipeline history initialization and clear operations so a second process cannot overwrite a concurrent first write.
- Hardened artifact index initialization and enforced the maximum artifact count inside the registration transaction.
- Changed local API signing-key creation to `AtomicJsonStore.read_or_create()`, preventing simultaneous first-run processes from replacing each other's key and avoiding repeated writes on token verification.

## Static checks

- Python AST syntax parsing completed for 10 changed Python modules.
- `git diff --check` passed. Git emitted line-ending normalization warnings only.
- **No tests were executed**, as requested.

## Remaining work / limitations

- This increment improves persistence consistency; it does not establish full Lumira completion.
- Multi-store operations such as artifact-index plus memory-index updates still need explicit reconciliation/repair semantics.
- OS sandbox execution remains fail-closed and must not be enabled until live guest isolation, network denial, resource limits, result integrity, and shutdown are independently accepted.
- Full requirement reconciliation, feature integrations, provider-backed voice/image/research, owner approvals, desktop acceptance, hardware acceptance and release readiness remain open.
- No files were staged, committed, pushed, reset, or deleted.
