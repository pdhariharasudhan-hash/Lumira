# Lumira open-source integration audit

**Audit date:** 2026-11-04
**Lumira baseline:** `a2bc0ca` on `main`
**Purpose:** reuse proven open-source implementations selectively while keeping Lumira's identity, data model, orchestration and safety boundaries.

## Repositories inspected

The following repositories were fetched as shallow, blob-filtered checkouts under `E:\\Lumira_OSS_Research`, outside the Lumira repository. No upstream dependencies were installed and no upstream files were copied into the live application during this audit.

| Project | Inspected revision | License inspected | Best-fit contribution | Integration decision |
|---|---|---|---|---|
| [Leon](https://github.com/leon-ai/leon) | `d61191bdf29c0b09d9dc041903a1921df664c0ac` | MIT | Agent run budgets/deadlines, cancellation, tool execution boundaries, context manager, memory manager, skill patterns | Adapt small language-independent design patterns into Lumira's Python Brain/autonomous-development services. Do not port the Node/TypeScript runtime wholesale. |
| [PyGPT](https://github.com/szczyglis-dev/py-gpt) | `a6766d0b2b7e839c2501f68575c1f00d7cfe012f` | MIT | Agent workflow lifecycle, extension manifest, configurable plugin options, model-callable tools, event hooks, audio/vision/chat workflows | Use the manifest/contract and lifecycle patterns as a reference for Lumira's future plugin foundation. Do not import its PySide6 desktop application into Lumira's Electron app. |
| [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | `eda0eb5e25a4facbe2ea92d86612a39618bcb54c` | MIT | OpenAI-compatible provider abstraction, model routing, attachment normalization, tool/agent plugin patterns, vector-store adapter boundary, document/RAG workflows | Adapt provider capability negotiation, context budgeting, retrieval interfaces and tests where Lumira has gaps. Do not replace Lumira's FastAPI persistence or duplicate its entire Node/Prisma stack. |
| [LocalAI](https://github.com/mudler/LocalAI) | `388be1fa1ddbef0e418ee89119245e6036b6f287` | MIT | Local inference runtime for LLM, vision, embeddings, audio and other model backends; OpenAI-compatible API/proxy patterns | Prefer an optional LocalAI runtime/provider adapter over embedding its Go/C++ runtime in the Lumira process. Keep model downloads and hardware requirements explicit. |
| [Open WebUI](https://github.com/open-webui/open-webui) | Not cloned in this audit | Custom license; prior review identified branding restrictions | UI interaction patterns only | No source copying or white-label reuse until the exact current license and deployment restrictions are reviewed. |

MIT source reuse requires retaining copyright and permission notices in copies or substantial portions. Each model/weight and transitive dependency has its own license and must be checked separately. Repository licenses do not automatically cover model weights, bundled assets, or third-party packages.

## Concrete source patterns inspected

### Leon
- `agent-run-budget.ts`: one non-renewable deadline shared across work, recovery and finishing; exposes remaining time, abort signal, timeout capping and explicit disposal.
- `agent-policy.ts`: central inference policy rather than scattering reasoning/streaming choices through agent steps.
- `tool-execution.ts`: central tool execution path with progress events, bounded observations and execution lifecycle.
- `context-manager` and `memory-manager`: context probes, context state, refresh worker, persistent retrieval and token-budget-aware selection.

**Lumira mapping:** autonomous-development run budgets and cancellation; central capability execution contract; context assembly and memory retrieval. Existing Lumira workspace boundary, change validation and fail-closed terminal gate remain authoritative.

### PyGPT
- `examples/addons/plugins/example_plugin/manifest.json`: declarative plugin identity/version/entrypoint metadata.
- `examples/addons/plugins/example_plugin/plugin.py`: explicit command allowlist, declared parameter schemas, options and event-driven dispatch.
- Agent controller and workflow monitor: explicit start/stop lifecycle and UI-consumer awareness.

**Lumira mapping:** future plugin manifest and capability declaration, explicit permissions, lifecycle, settings schema, event contract and user approval. External plugin code must not execute in the Lumira backend until a concrete sandbox and trust model are implemented.

### AnythingLLM
- `GenericOpenAiLLM`: provider configuration, model selection, capability flags, attachment normalization, context budgeting, streaming and usage reporting.
- `modelRouter`: a separate model-routing boundary.
- `vectorDbProviders/base.js`: common vector-store adapter contract.
- `agents/imported-manifest.schema.json` and imported-agent code: declarative extension validation.
- Agent plugins include memory, image generation, web browsing, filesystem and scheduled-job examples.

**Lumira mapping:** provider adapter/capability contract; safe model routing; common retrieval interface; extension manifest validation. Keep Lumira's existing memory/artifact/project stores as the source of truth rather than adding a second database system without evidence.

### LocalAI
- LocalAI exposes a broad local inference runtime and OpenAI-compatible surfaces for supported model backends.
- Its Go/C++ runtime is a separate deployable service with substantial native dependencies.

**Lumira mapping:** optional local endpoint support through a bounded OpenAI-compatible adapter, readiness checks, timeout/resource policies and modality-specific capability discovery. Do not bundle the entire LocalAI runtime into the 8 GB development laptop's desktop process.

## Lumira defects and integration gaps verified during this audit

1. **AI mode desktop integration is now present, but still needs packaged-app acceptance.** The desktop API client and Settings UI expose Offline/Hybrid/Cloud plus a separate cloud-consent control. Vite's development proxy and Electron's production API forwarder now include `/ai-mode`; the Electron forwarder was extracted into a testable module and verified with GET, PUT-body and backend-unavailable tests. The existing desktop `/modes` selector remains a separate task-category/session mode.
2. **Cloud permission is implemented for chat routing, not yet universal.** The provider-mode service and conversation router enforce local-first Hybrid behavior and require explicit consent before cloud chat use; focused service, route and UI tests cover these rules. This policy still needs to be applied and verified across image generation, voice, research and every other external-provider consumer. Existing `memory/ai_mode.json` remains `offline`; preserve it until the user deliberately changes it.
3. **Plugin/skill framework not found.** A source search under `app/`, `app/routes/` and the desktop source found no plugin/skill/extension directories, manifest loader or plugin registry. Do not mark the plugin framework complete.
4. **Multi-model registration requires verification.** The orchestrator and route exist, but the registry must be traced from application startup to actual registered providers and the normal chat path before the feature is described as operational.
5. **Feature registry is not proof of operational completion.** It has 28 internal entries; only 3 are currently enabled in the persisted registry snapshot. Provider, hardware, terminal isolation, web-fetch runtime, Tamil semantic acceptance and packaged desktop gates remain separate.
6. **Terminal execution remains correctly blocked.** Do not weaken its fail-closed guard to make a checklist green.
7. **Project preview currently registers a loopback URL; it does not launch a preview process.** Do not represent process launch as implemented.

## Frontend and desktop verification progress (2026-11-04)

- Added `/ai-mode`, `/providers` and `/resources` to the Vite development proxy; added `/ai-mode` to Electron's API route forwarding.
- Extracted Electron API forwarding into `lumira_desktop/electron-api-proxy.cjs` and included that module in the packaged file allowlist.
- Added regression tests for saved provider-mode loading/changes, explicit cloud consent, Notepad local persistence/backend save, all required Vite API roots and Electron request forwarding/error handling.
- Verified: TypeScript/Vite production build passes; Oxlint reports zero warnings/errors; 31 frontend tests pass; 3 Electron proxy tests pass; `git diff --check` reports no whitespace errors (only line-ending warnings).
- This is frontend integration evidence, not proof of a complete packaged desktop user journey. Electron launch/visual acceptance, real provider inference, optional modalities and the remaining feature groups are still outstanding.

## Integration rules

- Preserve Lumira's identity, Brain pipeline, project/memory/artifact formats and existing user data.
- Prefer small adapters and tested ports over importing another application's runtime.
- Every adapted source file must record its upstream project, path, revision, license and any modifications in `docs/third_party_notices.md`.
- Do not add a new framework dependency merely because an upstream project uses it.
- External plugin code and generated project code require verified OS-level isolation before execution.
- Provider registration, provider reachability and successful real model operation are three different states; report them separately.
- A source implementation is not complete until tests, desktop integration and the relevant real user journey pass.
- Keep cloud providers disabled until the user explicitly enables cloud use, regardless of Hybrid mode selection.
- Keep external research, image generation, transcription, speech, vision and hardware integrations visibly unavailable when their required providers/devices are absent.

## Next engineering sequence

1. Trace the normal chat path and every provider/model registry from startup to inference; design one enforceable provider-access policy with separate local/cloud permissions.
2. Complete packaged Electron user-journey verification for Offline/Hybrid/Cloud settings, including the local-only default, explicit consent, persistence and restart behavior.
3. Apply the central provider-access policy to every external modality, not just normal chat.
4. Add central run deadlines/cancellation and tool execution budgets to Lumira's existing autonomous-development/Brain pipeline, adapting Leon's bounded-budget pattern.
5. Define a manifest-only plugin contract from PyGPT/AnythingLLM patterns; keep execution disabled until sandboxing and permissions are independently verified.
6. Strengthen the existing retrieval/provider interfaces using AnythingLLM's adapter patterns without duplicating Lumira's stores.
7. Add LocalAI as an optional, separately managed local inference endpoint and validate memory/resource limits before model operations.
8. Re-run focused tests, then full backend and desktop suites; complete real provider, Tamil, hardware, recovery, sandbox and packaged-app acceptance.

**Audit status:** source inspection completed for the four MIT projects listed above. No upstream code has yet been copied into Lumira. The current working tree contains uncommitted source, tests and documentation changes, plus modified runtime state files (`data/project_memory.json`, `memory/activity_feed.json`, `memory/cognitive_sessions.json`, `memory/feature_registry.json`). Preserve those runtime files and do not commit them. No installer has been rebuilt or installed; packaged-app acceptance remains pending.

## Phase A integration applied (2026-11-06)

- Kept Lumira's existing Main Brain, cognitive modules, memory stores, provider registry, and local/cloud policy as the source of truth. No alternate agent runtime was installed or substituted.
- Normal open-ended conversation now passes through `BrainService.execute` and its validation/cognitive pipeline before a chat provider is invoked. A rejected or failed Brain run does not reach the provider. The Brain persists the user turn; the conversation route persists only the assistant turn to avoid duplicates.
- Added `ConversationContextService` to retrieve a small, read-only set of relevant Lumira goals, decisions, experiences, and learning records for normal chat. Archived records are excluded and sensitive fields are redacted. The context is explicitly labeled as reference data, not instructions.
- Added `ContextBudgetService`, adapting Nanobot's conservative UTF-8 byte-based prompt-cost estimation and bounded-history approach. Both local Ollama and OpenAI-compatible chat providers now preserve the newest valid user/assistant turns in chronological order under message, character, and estimated-cost limits.
- No mandatory dependencies were added. Nanobot is not imported at runtime; only the small adapted algorithm is used, with attribution in `docs/third_party_notices.md`.
- Focused Phase A verification is recorded in the development handoff; live provider inference still requires a configured and reachable provider. The user's persisted AI mode and cloud-consent settings were not changed.

## Phase A completion checkpoint — 2026-11-07

### Completed integration and bridge work
- Normal open-ended chat remains gated by a successful Main Brain run before the provider router can be constructed or called.
- Relevant, read-only memory context is now explicitly covered by a route-level regression test proving it is forwarded to the chat provider; archived/sensitive-memory filtering remains covered by the context-service tests.
- Local Ollama and explicitly consented cloud chat continue to use the centralized provider policy and bounded conversation history.
- Corrected the retry test fixture to declare retry_safe = True, matching the pipeline's explicit retry contract; the test now verifies recovery and learning history rather than failing because its test double lacked the required declaration.
- Removed a duplicate Nanobot attribution section while retaining the single MIT attribution and full license notice.

### Verification
- Conversation route/context/budget/provider tests: **25 passed**.
- Brain pipeline tests: **10 passed**.
- Provider-access policy/integration, AI-mode service/routes, and startup-registration tests: **23 passed**.
- Total focused Phase A and policy bridge verification: **58 passed**.
- git diff --check: passed; only pre-existing Git LF-to-CRLF notices were emitted.

### Explicit acceptance limits
- Real local Ollama inference has not been demonstrated in this pass. The earlier full backend run recorded 766 passed, 3 failed, and 1 skipped; one failure was the retry test-double contract corrected above. Two broader end-to-end validation tests still depend on a functioning local chat provider and reported local_provider_unavailable. The full suite was not repeated because available RAM fell to about 1.2 GB.
- A separate image-provider boundary test was attempted during the broader bridge check and was deferred by the resource guard (resource_pressure_deferred); this is not a Phase A conversation failure.
- Cloud mode/consent settings were not changed. No provider credentials, model settings, or runtime data were modified.
- Packaged Electron acceptance, real provider inference, and unrelated plugin/sandbox/modality gaps remain separate work and must not be represented as completed by this Phase A checkpoint.

**Phase A implementation status:** integrated and focused-test verified. **Live-provider acceptance:** pending a reachable local model and adequate RAM headroom. No commit, reset, cleanup, or user-data deletion was performed.


## Phase A acceptance recheck — 2026-11-07

- Reproduced the two previously reported `tests/test_validation.py` failures and isolated them to project-continuation tests invoking the real local chat provider without a test provider fixture. Added a deterministic, test-only continuation provider to those two tests so they verify project versioning, follow-up context, and session/memory recovery without requiring external inference. Both tests now pass (`2 passed in 18.08s`). The fixture does not change production provider behavior and does not count as live-model verification.
- Confirmed the local Ollama HTTP service responds to `/api/tags` and reports `qwen2.5-coder:3b` installed. No actual completion request was sent: available physical RAM fell to approximately 463 MB during the recheck, which is insufficient headroom to safely load the 1.9 GB model. Protecting the user's laptop took priority over forcing inference.
- The previously recorded 58 focused Phase A/policy tests remain the latest passing focused acceptance result. They were not rerun during this low-memory recheck. The complete backend suite was not rerun; the earlier run was 766 passed, 3 failed, 1 skipped, and one previously failing test fixture has since been corrected.
- **Status:** Phase A implementation and focused regression coverage are in place. Strict end-to-end acceptance is still open until one real local Ollama chat completion succeeds and the full backend suite is rerun with adequate memory. Do not describe Phase A as 100% accepted until those checks pass.
