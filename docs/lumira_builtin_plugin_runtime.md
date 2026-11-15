# Lumira built-in trusted plugin handlers

Lumira ships two application-owned, read-only handlers under the exact plugin ID `lumira.core`. They are not dynamically loaded plugins. The runtime binds them only after the owner explicitly registers and approves the matching manifest and permissions.

## Supported manifest

Retrieve the exact application-owned manifest from `GET /plugins/builtins/lumira-core/manifest`. Register it with `POST /plugins/builtins/lumira-core/register` and `{"confirm": true}`. This creates a pending metadata record only; it does not grant permissions or bind handlers. Alternatively, register the manifest below through `POST /plugins/register`:

```json
{
  "schema_version": 1,
  "plugin_id": "lumira.core",
  "name": "Lumira Core Read-only Tools",
  "version": "1.0.0",
  "api_version": "1",
  "description": "Application-owned read-only health and artifact metadata tools.",
  "capabilities": ["core.health_snapshot", "core.memory_summary", "core.memory_search", "core.memory_record_experience", "core.goal_create", "core.goal_decompose", "core.goal_update", "core.goal_list", "core.project_list", "core.artifact_list", "core.artifact_archive", "core.artifact_restore", "core.artifact_verify"],
  "permissions": ["device.read", "memory.read", "memory.write", "filesystem.project.read", "filesystem.artifacts.read", "filesystem.artifacts.write"],
  "dependencies": []
}
```

Then explicitly approve the two declared permissions using `POST /plugins/lumira.core/approve` with `confirm: true`. The approval route binds the known application handlers; application startup also rebinds them after restart. No handler is installed for any other plugin ID or unknown capability.

## Handlers

- `core.health_snapshot`: bounded, read-only system health snapshot; requires `device.read`.
- `core.memory_summary`: returns active record counts only, without record contents; requires `memory.read`.
- `core.memory_search`: searches cognitive memory with deterministic ranking; requires `memory.read`. Query is limited to 500 characters and at most 10 records per collection are returned.
- `core.goal_create`: creates a durable goal with bounded title, objective and priority; requires `memory.write` and a one-time argument-bound execution approval.
- `core.goal_decompose`: creates 1?20 child objectives under an existing active goal; requires `memory.write` and a one-time argument-bound execution approval.
- `core.goal_list`: returns at most 50 active goal metadata records with optional text/status filters; requires `memory.read`.
- `core.goal_update`: updates an existing goal's status, progress and/or blockers; requires `memory.write` and a one-time argument-bound execution approval. Completing a goal sets progress to 100 when progress is omitted.
- `core.memory_record_experience`: writes a bounded experience record; requires `memory.write` and a one-time argument-bound execution approval. It always stores `verified: false`; it cannot self-certify outcomes.
- `core.project_list`: returns at most 50 project names and version counts; requires `filesystem.project.read`. It never returns source files or paths.
- `core.artifact_verify`: checks an artifact's stored file against its checksum without returning file content; requires `filesystem.artifacts.read`.
- `core.artifact_archive` and `core.artifact_restore`: archive or restore an artifact without deleting or changing its content; require `filesystem.artifacts.write` and a one-time argument-bound execution approval. Permanent deletion is deliberately not exposed.
- `core.artifact_list`: returns at most 50 artifact metadata records; requires `filesystem.artifacts.read`. It never returns storage paths, file names or artifact contents. Optional filters are `limit`, `artifact_type`, and `include_archived`.

Use `GET /plugins/runtime/handlers` or `GET /brain/plugins/capabilities` to inspect currently bound handlers. The Brain discovery endpoint lists only reconciled handlers and provides their Brain execution paths; approved manifest capabilities without a trusted handler are deliberately omitted. Invoke through `POST /brain/plugins/lumira.core/capabilities/{capability}/execute`; requests must include `confirm: true`, a valid session, and a Brain message that passes explicit verification. For `core.goal_create`, `core.goal_decompose`, `core.goal_update`, `core.memory_record_experience`, `core.artifact_archive` and `core.artifact_restore`, first obtain a one-time approval from `POST /plugins/lumira.core/capabilities/core.memory_record_experience/approval` with `confirm: true`, the same session ID, and the exact arguments; pass the returned approval ID and unchanged arguments to the Brain execution endpoint. The normal runtime then rechecks plugin grants and writes execution audit records.

Revoking either permission or disabling the plugin causes runtime reconciliation to evict the handler. The handlers are sequentially bounded by the shared tool execution capacity and result-size policy.
