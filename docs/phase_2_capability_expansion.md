# Phase 2 — Capability Expansion (Handoff 10)

Status: implementation coverage completed; behavioral and provider/hardware acceptance pending.

This is the revised Phase 2 scope agreed for Handoff 10. It is separate from Project Continuation V1 and desktop Phase 4.

## 10.1 — Feature Registry

- Persistent catalog, normalized feature IDs/aliases, dependency metadata, provider requirements, health state, enable/disable state, and migration of missing catalog entries are implemented in the existing FeatureRegistryService.
- Added the missing `audio_playback` catalog feature with explicit voice-input and artifact-manager dependencies.
- Registry state remains persisted in `memory/feature_registry.json`; adding the catalog item is handled by the existing additive registry migration on next service initialization.

## 10.2 — Feature Activation Engine

- Dependency-aware direct activation, dependency planning, status, listing, deactivation protection, provider readiness and terminal isolation gates are present.
- Dependency-bridge activation now preflights the full dependency chain and writes all enabled states in one registry write. A provider blocker no longer leaves unrelated dependencies partially activated.
- Read-only dependency plans now evaluate the entire proposed activation order, rather than incorrectly treating dependencies in that same plan as missing.
- Natural-language `Lumira activate ...` commands now use the dependency bridge.
- Added regression cases for atomic preflight, dependency-plan readiness, and identity-to-registry resolution.

## 10.3 — Lumira Identity and Language

- The protected Lumira identity/system prompt and explicit identity command parser are present.
- English, Tamil Unicode and a bounded romanized-Tamil lexicon are detected by the existing LanguageDetectionService; mixed-script and Tamil-English input are labelled separately.
- The `audio playback` identity alias now resolves to a real catalog feature instead of a missing registry ID.
- Romanized Tamil detection is intentionally lexicon-based; it is not a claim of complete Tamil semantic understanding.

## 10.4 — Artifact Manager and Storage

- Existing ArtifactManagerService stores text and validated binary artifacts, maintains an indexed catalog, checks signatures and path containment, and supports retrieval, search, archive, restore, deletion, statistics and integrity reporting.
- Supported categories include audio, transcripts, summaries, images, diagrams, blueprints, schematics, exports, reports, video, PDF and generated files.
- The desktop Artifact Manager already includes multi-file import, metadata search, paging, detail/content preview, and media/PDF previews.

## 10.5 — Voice Idea Capture

- Existing voice capture accepts bounded WAV, MP3, M4A, OGG and WebM uploads and stores recordings as audio artifacts.
- Existing voice pipeline connects transcription, language detection, summary generation, artifact storage and memory; retry endpoints preserve previously saved artifacts.
- Wake-word listening is opt-in and provider/hardware-dependent. Detection queues an activation event; it does not directly execute commands.
- Audio artifact playback is available through the existing artifact content route and desktop native audio controls.
- Fixed a concrete pipeline defect: voice ideas previously used an unsupported memory experience type, which could fail after audio/transcript/summary creation. They now use the supported workflow experience type, remain unverified for learning consolidation, and report recoverable memory-write failures without losing saved artifacts.
- Local Faster-Whisper now declares support for the full set of stored audio formats. The OpenAI-compatible transcription adapter supports WAV, MP3, M4A and WebM; OGG remains local-provider-only. TranscriptService now returns a specific unsupported-format result before invoking an incompatible provider, and the voice route maps that to HTTP 422.

## 10.6 — Memory Expansion

- Existing cognitive memory supports bounded goals, decisions, experiences, learning records, links, artifact references, scoped retrieval, summaries, archive/verification and verified-experience learning consolidation.
- Voice ideas are stored as unverified workflow experiences linked to their audio, transcript and summary artifacts. They do not become learned success/failure rules merely because a recording was captured.

## 10.7 — Image Generation

- Existing image-generation route/service uses the configured provider registry and provider-access policy, validates image bytes/signatures and size, and stores successful output as binary artifacts.
- Image generation is provider-dependent and defers optional rendering under memory pressure. No claim is made that a provider/API key is configured or that a live image has been rendered in this acceptance pass.

## 10.8 — Unified Search

- Existing UnifiedSearchService searches projects and versions, generated source files, workspace source/docs, artifacts, memory, feature/pipeline history, sessions/conversations, goals, decisions, experiences, learning, notes, workflows, devices and research.
- Public search sanitizes internal filesystem paths.
- Fixed an empty-query response-shape gap: the empty result now includes the same `research` category as non-empty results.

## Verification and remaining acceptance

- Python AST parsing passed for all 16 changed implementation/test files in this Phase 2 continuation.
- `git diff --check` passed; Git emitted only existing LF-to-CRLF working-copy notices.
- Regression tests were added/updated but were not executed, in line with the project's current instruction not to run tests/builds/runtime checks without explicit approval. Free RAM was approximately 1.01 GB at the static-check pass.
- No live transcription, summarization, wake-word, speech, or image provider was invoked. Provider keys, local model availability, microphone access, and actual media playback require runtime acceptance.
- No BIOS/UEFI or Windows settings were changed. The project-controlled terminal remains disabled until genuine per-run OS isolation is implemented and verified.
- No commit, push, reset, cleanup, feature-flag bulk activation, or user-data deletion was performed.

Verdict: Phase 2 implementation gaps found in this review have been corrected and regression coverage authored. Do not label Phase 2 fully runtime-verified until the focused tests and provider/hardware acceptance pass.


## Cross-phase Brain execution hardening — 2026-11-05

- Added a per-execution control object and in-process registry with a 120-second default deadline, a 600-second hard maximum, and session-scoped cooperative cancellation.
- BrainExecutor now checks cancellation/deadline before and after each synchronous stage, records explicit cancelled / timed_out states, enforces the 1–12 module bound and a 36-attempt ceiling, and rejects module return values other than BrainState or None.
- Retries now require an explicit retry_safe = True declaration. The built-in cognitive modules are not opted in by default because their service/provider calls may be billable or have side effects; Learning is explicitly non-retryable. Resume uses the same fail-closed retry rule.
- BrainService persists cancelled, timed-out and failed runs as unsuccessful instead of allowing final validation to turn them into success. Added POST /brain/cancel/{session_id} to request cancellation for active runs in that session.
- Added focused tests for expired deadlines, cancellation before/between stages, retry safety, registry cleanup and the cancellation route. Focused result: 8 passed (including the existing recovery retry regression).
- Python compileall passed for the touched Brain modules/routes/tests. git diff --check passed; only existing LF-to-CRLF notices were emitted.
- Important limit: cancellation is cooperative between stages. A currently running synchronous provider/service call cannot be preempted until it returns. No full repository suite, provider calls, microphone/hardware checks, desktop build, or packaged-app acceptance was run in this pass.

This is a cross-phase correctness improvement, not a declaration that Phase 1 or Phase 2 is complete. Provider, UI, hardware, isolation and full acceptance gates remain open.


## Additional focused verification — 2026-11-05

- Phase 2 feature registry, dependency activation, command routing, voice idea pipeline, transcription-format compatibility, OpenAI-compatible transcription and Unified Search tests: **51 passed**.
- Phase 1 provider-policy, provider-boundary, chat routing, OpenAI-compatible chat, AI-mode route/service and command-conversation integration tests: **37 passed**.
- Brain execution-control and recovery tests: **8 passed**.
- Combined selected regression evidence: **96 passed, 0 failed** across these three focused runs. These are targeted suites, not a full repository run.
- No live cloud API, local model inference, microphone, wake-word hardware, image-generation provider, packaged Electron installer, or end-to-end desktop acceptance was exercised. Do not mark either phase fully complete from these unit/regression results.


## Cross-phase verification update — 2026-11-05

- BrainExecutor.execute() now delegates to the same bounded/validated traced execution path, so untraced callers cannot bypass module-count, result-type, attempt-budget or retry-safety rules.
- BrainExecutor.resume() now rejects boolean stage indices, bounds pipeline size and total attempts, validates module return types, honors verification rejection, records completed state, and retries only modules that explicitly opt into retry safety.
- Added desktop API/client and composer control for requesting cooperative cancellation of the active Brain session. The UI states that cancellation takes effect at the next stage boundary and cannot preempt a currently running synchronous provider call.
- Focused backend regression tests now pass **99/99** across Phase 1 provider/chat policy, Phase 2 Handoff 10 capabilities, and Brain execution/recovery.
- Complete desktop test suite passes **34/34** across 5 files; lint reports 0 warnings/errors; production TypeScript/Vite build passes.
- Python compileall for app and tests and git diff check pass. Git reports only existing LF-to-CRLF working-copy notices.
- Full backend suite, packaged Windows installer, live cloud/local inference, microphone/speaker/wake-word hardware, live image generation and visual desktop acceptance were not run. These are release/provider/hardware gates, not covered by the focused test results.


## Expanded Phase 1 / Phase 2 verification — 2026-11-05 (latest)

- Expanded the safe focused backend matrix to cover audio playback, artifact queries/recent artifacts, voice interactions/history/recovery/memory retry, voice route readiness, wake-word activation/listener, image-generation routes/resource deferral, memory lifecycle, Unified Search, output adaptation, provider startup registration and greeting behavior.
- Added same-language response guidance to Lumira's protected system prompt: respond in the user's language when possible, including Tamil Unicode, romanized Tamil and Tamil-English mixed input; preserve technical terms; clarify ambiguous romanized Tamil rather than guessing.
- Expanded the bounded romanized-Tamil lexicon with common first-person forms (including irukken/iruken/irukiren/irukkiren) and added pure-Tamil, romanized-Tamil and English-vs-Tamil regression coverage.
- Brain failure paths now clear current_stage when marking execution failed. Added a BrainService regression proving cancelled execution is persisted and returned as unsuccessful and its execution-control registration is released.
- Latest combined backend focused matrix: **190 passed, 0 failed**. This matrix deliberately excludes tests that execute generated project code and is not the full repository suite.
- Desktop Vitest remains **34 passed / 0 failed**; lint 0 warnings/errors; production build passed. Full Python compileall and git diff check passed.
- Tamil language labels and prompt guidance do not prove semantic quality for every Tamil dialect or a real model's Tamil fluency. Actual local/cloud inference and native hardware/provider acceptance remain required.


- Final API registration smoke test: the real FastAPI application exposes POST /brain/cancel/{session_id}; route test passes. Brain execution-control suite: 12 passed. Latest backend focused matrix count is now 191 passing tests when including this additional API registration check; earlier 190-test combined run remains the broad matrix baseline.


## 2026-11-10 — Live multimodal acceptance continuation

- Local Faster-Whisper tiny-model transcription now runs on the installed PyAV build. The provider decodes audio to a 16 kHz float32 waveform to avoid the incompatible `metadata_errors` keyword, and uses an initial prompt to improve the assistant-name recognition. Live English transcription passed on a Windows-generated WAV; Tamil speech and physical microphone capture remain unverified.
- A live end-to-end voice idea pipeline completed: audio artifact -> local transcript -> language detection -> Ollama summary -> cognitive-memory experience with artifact links. The run used isolated temporary storage and did not modify project memory.
- Local Moondream image understanding completed through `ImageUnderstandingService` and saved a report artifact. The adapter was corrected from `/api/chat` to `/api/generate` because the installed Moondream chat endpoint returned empty content.
- Summary generation was exercised through `SummaryService` using the real local Ollama Qwen model; output was persisted and its artifact checksum verified.
- These are local provider acceptance results, not proof of microphone/speaker hardware, Tamil speech quality, live image-generation, TTS or external research provider acceptance.
