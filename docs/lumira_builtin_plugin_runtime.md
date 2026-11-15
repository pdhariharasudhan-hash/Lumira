# Lumira built-in trusted plugin handlers

Lumira provides application-owned handlers under six separate permission scopes plus one local language-classification plugin that requests no privileged permission. The scopes are separate so approving a read capability never requires granting memory or artifact write access. No third-party plugin code is imported or executed.

## Register the built-in manifests

1. Retrieve the exact manifests from `GET /plugins/builtins/lumira-core/manifest`.
2. Register all six pending manifests with `POST /plugins/builtins/lumira-core/register` and body `{"confirm": true}`. Registration creates metadata only; it grants no permissions and binds no handlers.
3. Approve only the permission scopes you actually want, using `POST /plugins/{plugin_id}/approve` with `confirm: true` and the exact permission in `granted_permissions`. Each manifest has one permission, so scopes can be enabled independently.
4. The approval route binds the known application handlers. Application startup rebinds approved handlers after restart.

## Permission scopes and capabilities

| Plugin ID | Permission | Capabilities |
|---|---|---|
| `lumira.core.language` | None (explicit owner approval still required) | `core.language_classify` |
| `lumira.core.system` | `device.read` | `core.health_snapshot`, `core.provider_status` |
| `lumira.core.memory.read` | `memory.read` | `core.memory_summary`, `core.memory_search`, `core.goal_list`, `core.todo_list`, `core.note_list` |
| `lumira.core.memory.write` | `memory.write` | `core.memory_record_experience`, `core.memory_archive`, `core.memory_link`, `core.goal_create`, `core.goal_decompose`, `core.goal_update`, `core.todo_create`, `core.todo_update`, `core.note_create`, `core.note_update`, `core.todo_create`, `core.todo_update`, `core.note_create`, `core.note_update`, `core.note_create`, `core.note_update` |
| `lumira.core.projects.read` | `filesystem.project.read` | `core.project_list` |
| `lumira.core.artifacts.read` | `filesystem.artifacts.read` | `core.artifact_list`, `core.artifact_verify` |
| `lumira.core.artifacts.write` | `filesystem.artifacts.write` | `core.artifact_archive`, `core.artifact_restore` |

The language classifier uses local deterministic rules for Tamil script, romanized Tamil and English prefixes; it does not upload text to an external provider.

## Handler behavior

- `core.language_classify`: returns detected language, intent, confidence and classification source for text up to 10,000 characters.
- `core.health_snapshot`: bounded, read-only system health snapshot.
- `core.provider_status`: reports configured provider names and implementation types only; it makes no network calls and never exposes credentials.
- `core.memory_summary`: active cognitive-memory record counts only.
- `core.memory_search`: deterministic memory search; query up to 500 characters and at most 10 records per collection.
- `core.goal_list`: at most 50 goal metadata records with optional text/status filters.
- `core.memory_record_experience`: records a bounded experience; always stores `verified: false`.
- `core.memory_archive`: archives a goal, decision, experience or learning record with a required reason; it never permanently deletes the record.
- `core.memory_link`: creates an explicit relationship between two existing, active cognitive memory records; endpoint IDs are checked before linking.
- `core.goal_create`: creates a durable goal with title, objective and priority.
- `core.goal_decompose`: creates 1?20 child objectives under an existing active goal.
- `core.goal_update`: updates goal status, progress and/or blockers; completing a goal sets progress to 100 if omitted.
- `core.todo_list`: lists at most 50 personal tasks with optional status filtering.
- `core.todo_create`: creates a personal task with priority and optional project/blocker metadata.
- `core.todo_update`: updates task progress; 100% automatically marks the task completed.
- `core.note_list`: lists at most 50 note titles and timestamps without note contents.
- `core.note_create`: creates a personal note with bounded title and content.
- `core.note_update`: updates the title and/or content of an existing note.
- `core.project_list`: at most 50 project names and version counts; no source files or paths.
- `core.artifact_list`: at most 50 artifact metadata records; no storage paths, file names or content.
- `core.artifact_verify`: verifies stored artifact content against its checksum without returning the content.
- `core.artifact_read_text`: reads at most 20,000 characters from a non-archived text artifact after one-time argument-bound approval; it verifies the checksum and never returns file paths or binary media.
- `core.voice_consent_status`: reports explicit capture, storage, transcription and retention flags for a saved audio artifact without reading audio content or exposing the consent receipt ID.
- `core.artifact_archive` and `core.artifact_restore`: archive or restore without deleting or changing artifact content. Permanent deletion is not exposed.

All write capabilities and text-artifact reads require a one-time, argument-bound execution approval in addition to the plugin permission grant. First call `POST /plugins/{plugin_id}/capabilities/{capability}/approval` with `confirm: true`, the session ID and exact arguments. Then pass the returned approval ID and unchanged arguments to the Brain execution endpoint.

## Brain discovery and execution

Use `GET /plugins/builtins/lumira-core/status` to see registration, approval and binding state for each permission scope. Use `GET /brain/plugins/capabilities` to inspect only currently bound, reconciled handlers. The discovery response includes each tool's validated JSON parameter schema and approval requirement, so a Brain client can construct a schema-conformant invocation without guessing. Invoke a handler through `POST /brain/plugins/{plugin_id}/capabilities/{capability}/execute`. The request requires `confirm: true`, a valid session, a Brain message that passes explicit verification, and (for write handlers) the one-time approval ID. The runtime rechecks plugin grants and records execution audit events.

Revoking a permission or disabling a plugin evicts its in-process handlers. The handlers use the shared bounded tool execution capacity and result-size policy.
