# Project Continuation V1

## Scope

Project Continuation V1 continues an existing saved API project instead of treating a follow-up as a brand-new project. It resolves the latest saved version, loads its metadata and source files, plans the requested change, asks the configured Lumira code-chat provider to update the project, validates the complete proposed file set, saves a new version, and records the continuation in project history.

## Flow

1. Resolve the project from the active session or explicit project name.
2. Select the latest saved version. The direct continuation API also accepts an explicit version for deliberate version-based work.
3. Read the version's metadata and bounded source files through the existing safe project-path resolver.
4. Validate source names, file counts, per-file size, total size, and required V1 API files.
5. Run the existing Builder and Execution planning stages. A rejected plan stops continuation.
6. Send the instruction, recent prior change requests, plan, and existing source files to `ConversationProviderRouter`. Existing source files are untrusted data, not instructions.
7. Require a strict JSON response containing a summary and the complete contents of every existing file plus any new files.
8. Reject malformed output, omitted existing files, unsafe filenames, oversized files, empty content, no-op output, or source-validation failures. No new version is saved on these failures.
9. Save the accepted result through the existing staged `ProjectWriter`, producing the next version and recording the previous version, instruction, summary, and changed filenames in project history.
10. Update the active session to the new version only after a successful save.

## Provider and privacy behavior

- The continuation uses the existing AI-mode/provider-access policy.
- Local Ollama is preferred in Hybrid mode. External/cloud providers remain blocked unless the user has explicitly enabled cloud access and selected an allowed mode.
- If no authorized provider is available, continuation returns an explicit unavailable result. It does not silently fall back to metadata-only regeneration.
- Source files are included in the model request. Users should not send secrets in project source; generated output is checked for file/path boundaries but is not a substitute for a security review.

## V1 boundaries

- User instructions are capped at 1,500 characters, source context at 4,000 characters, the complete provider prompt at 9,500 characters, and provider output at 12,000 characters.
- Files are flat project-root files; nested directory output is not supported by the current ProjectWriter contract.
- The existing CodeValidationService requires `main.py`, `requirements.txt`, Python syntax validity, and the V1 FastAPI CRUD route contract.
- Generated code is not executed. The project terminal remains disabled until independently verified OS-level isolation is available.
- This is a bounded V1 continuation path, not a claim that arbitrary repositories or unlimited projects can be autonomously modified.

## Verification status

- Focused regression tests were added for source-aware editing, latest-version selection, preserving existing files, refusing omitted files, refusing invalid/no-op generated code, and the prompt/source-context limits.
- Python AST parsing passed for the changed service, lifecycle, route, command, and test files.
- `git diff --check` passed; Git emitted existing LF-to-CRLF working-copy notices.
- Behavioral tests were not run. The host currently reports about 1.16 GB free RAM, and Windows firmware virtualization, VM monitor extensions, and SLAT are disabled. The repository's verification policy requires a disposable OS-isolated environment for project-controlled tests.


## Verification update — 2026-11-06

- Executed the focused mocked/service-level suite `tests/test_project_continuation_service.py`: **7 passed, 0 failed**.
- Python byte-compilation passed for the continuation service, lifecycle service, API route, provider router, project writer, and focused test module.
- `git diff --check` passed. Git emitted only existing LF-to-CRLF working-copy notices.
- The focused tests validate source-aware continuation, latest-version selection, preservation of existing files, refusal of omitted/invalid/no-op output, syntax rejection, and source-context limits. The test provider and writer are fakes; this does not prove live model output quality or a real disk save.
- Host free RAM was approximately 0.8 GB before the focused test and 1.22 GB afterward. No broad suite, frontend build, packaging, or live provider inference was attempted.
- Generated project code was not executed. OS-level per-run isolation remains unverified, so terminal execution remains disabled.
- Phase 3 implementation and focused service-level verification are complete; deployment/provider/security acceptance remains open.
