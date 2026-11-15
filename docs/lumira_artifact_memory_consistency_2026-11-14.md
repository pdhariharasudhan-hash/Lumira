# Artifact index and memory-mirror consistency

## Design
- `memory/artifact_index.json` is the canonical artifact metadata index.
- `MemoryService`'s `artifacts` collection is a derived searchable mirror; it must never be treated as the authority for artifact ownership, content paths, or checksums.
- `ArtifactMemoryConsistencyService.reconcile()` provides a bounded, read-only preview by default. An explicit internal caller may pass `apply=True` to perform idempotent mirror repair.
- Repair adds missing mirror records, removes stale mirror records, and replaces mismatched or duplicate mirror records from canonical metadata. Canonical duplicate IDs are not auto-repaired: they are reported as failures because selecting a winner would risk data loss.
- The HTTP surface exposes only `GET /artifacts/consistency`; no unauthenticated repair endpoint was added.

## Response fields
- Counts for missing, stale, mismatched and duplicate IDs.
- A bounded list of affected artifact IDs (never local file paths).
- `read_only`, `mutations_performed`, per-action counts, failures and remaining findings.

## Operational limitation
This is a cross-store repair primitive, not a distributed transaction. Each mirror update is atomic at the memory-store level, but a process crash can interrupt a multi-record repair. Re-running the operation is intended to converge the mirror. A future durable outbox/journal and owner-authenticated maintenance action are still required for stronger crash recovery and remote repair.

## Validation policy
No tests were run for this increment, as explicitly requested. Static syntax parsing and diff hygiene only are performed separately.
