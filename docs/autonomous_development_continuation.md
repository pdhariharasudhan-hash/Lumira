# Continue Lumira Development

After a Copilot session ends, continue from the repository with:

```powershell
python ai.py develop "Continue Lumira development"
```

`Continue`, `Continue Lumira development`, and `Complete remaining Lumira development` use the same continuation path.

Lumira stores its development program and task backlog in `memory/development_backlog.json`. The backlog is structured, atomically persisted, and records task objectives, priority, dependencies, relevant files, acceptance criteria, allowed validation commands, attempts, iteration, the latest error/validation, and recovery identifiers. Do not delete this file to restart a program; completed tasks and structured lessons are part of the handoff.

Each invocation runs a bounded audit, refreshes the existing program without duplicating tasks, selects up to three dependency-ready tasks by priority, and runs the existing safe development workflow. Per task, the existing `RunRecoveryService` records stages and safe resume points. If an interruption occurs, run the continuation command again; provider-generation and validation checkpoints can resume, while an uncertain file-application checkpoint is blocked for reconciliation instead of being repeated.

The model receives only relevant bounded source context. Changes still pass `WorkspaceBoundary`, `ChangeApplier`, exact old-content validation, the command allowlist, pytest validation, and final verification. The provider receives at most two attempts per generation. Task attempts are capped; blocked tasks retain their error and lessons while independent ready tasks can proceed.

If no evidence-backed task is available, or every remaining task is blocked, Lumira records and reports that state rather than claiming the development program is complete. The current audit covers bounded source TODO/FIXME evidence and persisted recoverable development runs; it does not yet cover every backend, desktop, artifact, voice, search, session, and mode integration. Consequently, it deliberately cannot mark the whole Lumira program complete until a verified whole-program audit reports `completion_ready=true`.