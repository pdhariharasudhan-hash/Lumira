# Lumira

Lumira is a local personal AI core with a FastAPI backend and a separate
React/Vite desktop workbench. `/command` runs the cognitive Brain first, then
routes the request through mode and capability policy. Project generation
uses validate → builder → execution plan → code generation → source validation
→ versioned save. Failed or incomplete stages stop the pipeline; generated
projects are not reported as complete until their files validate and save.

## Quick start (Windows)

After the project virtual environment and desktop dependencies already exist, launch both services with one command from the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\start_lumira.ps1
```

The launcher checks for the existing Python environment and desktop dependencies, reuses services that already respond on the expected loopback ports, and opens separate windows for services it starts. It does not install packages or change system settings. Open `http://127.0.0.1:5000` in your browser and keep the service windows open.

If dependencies are not installed yet, follow the manual setup below first.

## Run the backend

From the repository root:

```bash
pip install -r requirements.txt
python run.py
```

The backend listens on `127.0.0.1:8000` by default. `PORT` and `RELOAD` can
be set through environment variables. `HOST` can be set explicitly when
needed; the API has no multi-user authentication and should stay on a trusted
local interface. Browser requests carrying a non-loopback `Origin` are rejected,
but this is not a substitute for deployment authentication. Do not bind the
backend to a LAN interface. The FastAPI application is `app.main:app`; the root
`main.py` is an unrelated legacy sample.

## Run the desktop workbench

In a second terminal:

```bash
npm ci --prefix lumira_desktop
npm --prefix lumira_desktop run dev -- --host 127.0.0.1 --port 5000
```

The Vite development server proxies all desktop API roots—including Brain,
Command, intelligence, image analysis, modes, features, notepad, sessions,
memory, projects, artifacts, search, workflows, runs, voice, devices, and health—
to the backend on port `8000`.
Keep the development server bound to loopback. Do not override it with
`--host 0.0.0.0` on an untrusted network: the proxy could expose the backend's
loopback-trusted API to other devices.

## Optional local Ollama summarization

The transcript summarizer can use Ollama's OpenAI-compatible local endpoint.
Install/start Ollama and pull a model first (the default is `qwen2.5-coder:3b`).
In the same PowerShell terminal used to start Lumira, enable the adapter:

```powershell
$env:LUMIRA_OLLAMA_SUMMARY_ENABLED = "1"
$env:LUMIRA_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
$env:LUMIRA_OLLAMA_MODEL = "qwen2.5-coder:3b"
python run.py
```

This enables transcript summarization only. Speech-to-text, speech synthesis,
image generation, and sourced web research each have separate opt-in providers
below; an opt-in Picovoice provider detects Lumira in uploaded WAV recordings
and can listen continuously when both optional audio packages are installed.
Input and output sizes
are bounded, provider errors are returned without exposing credentials, and
successful summaries continue through Artifact Manager.

## Optional offline speech-to-text (faster-whisper)

For local transcription without sending recordings to a remote API, install the optional dependency from the project root:

```powershell
python -m pip install -r requirements-local-transcription.txt
$env:LUMIRA_LOCAL_TRANSCRIPTION_ENABLED = "1"
$env:LUMIRA_LOCAL_TRANSCRIPTION_MODEL = "base"
$env:LUMIRA_LOCAL_TRANSCRIPTION_COMPUTE_TYPE = "int8"
$env:LUMIRA_LOCAL_TRANSCRIPTION_CPU_THREADS = "2"
python run.py
```

The model loads on the first transcription request, not during API startup. The default `base` model with CPU `int8` is chosen to reduce memory use on an 8 GB laptop; first use may download model files, so keep enough disk space and internet access for that initial download. For fully offline use, download the model once and set `LUMIRA_LOCAL_TRANSCRIPTION_MODEL_PATH` to its local model directory. You may set `LUMIRA_LOCAL_TRANSCRIPTION_MODEL_CACHE` to move cached model files off the system drive. Local transcription respects Lumira's resource-pressure guard and can be deferred when RAM is constrained. Local mode takes precedence over the remote transcription provider if both are enabled. The upstream faster-whisper project is MIT-licensed; see [`docs/third_party_notices.md`](docs/third_party_notices.md).

## Optional speech-to-text provider

Lumira can send uploaded WAV, MP3, or M4A audio to an OpenAI-compatible
transcription endpoint. This is opt-in, uses the configured endpoint over HTTPS
(except loopback URLs for local gateways), and does not download a speech model.
Set credentials only in the local PowerShell session used to launch Lumira; do
not put API keys in source files or commit them:

```powershell
$env:LUMIRA_TRANSCRIPTION_ENABLED = "1"
$env:LUMIRA_TRANSCRIPTION_API_KEY = "your-provider-api-key"
$env:LUMIRA_TRANSCRIPTION_BASE_URL = "https://api.openai.com/v1"
$env:LUMIRA_TRANSCRIPTION_MODEL = "whisper-1"
python run.py
```

The default endpoint/model are examples for an OpenAI-compatible transcription
API. Provider model availability, pricing, account access, and language support
must be confirmed with the chosen provider. Lumira caps audio at 25 MB and
transcription responses at 1 MB, bounds request time and transcript size,
sanitizes request errors, and stores successful transcripts through Artifact
Manager. Without the enable flag and a key, no
transcription network request is made and the route retains its explicit
provider-unavailable response.

## Optional speech synthesis

Speech playback can use an OpenAI-compatible text-to-speech endpoint. Enable it
only when you have a valid provider key; configure it in the local PowerShell
terminal used to launch Lumira:

```powershell
$env:LUMIRA_SPEECH_SYNTHESIS_ENABLED = "1"
$env:LUMIRA_SPEECH_API_KEY = "your-provider-api-key"
$env:LUMIRA_SPEECH_BASE_URL = "https://api.openai.com/v1"
$env:LUMIRA_SPEECH_MODEL = "tts-1"
$env:LUMIRA_SPEECH_VOICE = "alloy"
python run.py
```

The adapter requests MP3 output, streams it with a 25 MB limit, validates the
MP3 signature, and stores successful audio through Artifact Manager. It accepts
`en`, `ta`, and `ta-en` request labels; those labels do not guarantee every
provider/model has equal support for each language. Confirm the selected
provider's model, voice, language coverage, and pricing. No key is stored in
source code, and the provider remains unavailable unless both the enable flag
and API key are set.

## Optional local image understanding (Ollama)

For image descriptions and OCR-like inspection without sending images to a remote provider, install/start Ollama, pull a vision model, then enable the local adapter in the same PowerShell session used to start Lumira:

```powershell
ollama pull moondream
$env:LUMIRA_OLLAMA_VISION_ENABLED = "1"
$env:LUMIRA_OLLAMA_VISION_MODEL = "moondream"
$env:LUMIRA_OLLAMA_VISION_BASE_URL = "http://127.0.0.1:11434"
python run.py
```

The adapter uses Ollama's local `/api/chat` endpoint, accepts PNG/JPEG/WebP images up to 10 MB, caps prompts and responses, and rejects non-loopback endpoints. The default model is `moondream` to avoid selecting a large vision model by default, but actual memory use and image-analysis quality depend on the installed model and hardware. Model downloads happen through Ollama, not during Lumira API startup. Local Ollama vision takes precedence over the remote vision provider when explicitly enabled and still respects Lumira's resource-pressure gate. Ollama is MIT-licensed; see [`docs/third_party_notices.md`](docs/third_party_notices.md).

## Optional image generation

Image generation can use an OpenAI-compatible images endpoint. Set the provider
key in the local PowerShell terminal and enable the adapter explicitly:

```powershell
$env:LUMIRA_IMAGE_GENERATION_ENABLED = "1"
$env:LUMIRA_IMAGE_API_KEY = "your-provider-api-key"
$env:LUMIRA_IMAGE_BASE_URL = "https://api.openai.com/v1"
$env:LUMIRA_IMAGE_MODEL = "gpt-image-1"
python run.py
```

The adapter requests one 1024×1024 image, accepts a bounded base64 image response,
validates PNG/JPEG/WebP signatures, and stores valid image bytes through the
existing Image Generation Service and Artifact Manager. The default model and
endpoint are examples: confirm access, supported response format, price, and
model availability with your provider. Remote image generation is not tested
until a real provider key is configured; without the enable flag and key, Lumira
continues to report that no image provider is available.

## Optional sourced web research

Lumira's research capability can use the Tavily search API to retrieve current
web results with source URLs. Enable it only when you have a Tavily API key:

```powershell
$env:LUMIRA_RESEARCH_ENABLED = "1"
$env:LUMIRA_RESEARCH_API_KEY = "your-tavily-api-key"
python run.py
```

The adapter caps the query at 4,000 characters, streams at most 5 MB of
response data, requests at most 10 results, keeps total findings within 100,000
characters, keeps HTTPS source URLs, removes duplicates, and sanitizes network
errors. It is registered as the `research` provider, so the
existing research service validates its findings and sources before returning
them. The adapter does not browse arbitrary URLs or treat page text as trusted
instructions. Provider account access, rate limits, and pricing are external
requirements. Without the enable flag and key, external research remains
explicitly unavailable rather than fabricating results.

## Direct web fetch (experimental)

`POST /web/fetch` accepts a JSON body such as `{ "url": "https://example.com/" }` and returns bounded page text, filtered HTTP(S) links, status metadata, and an artifact reference for supported successful binary downloads. It rejects unsupported schemes and credential-bearing URLs, blocks localhost and DNS answers that are not globally routable, revalidates redirects, disables environment proxy use, caps downloads at 10 MB, and redacts common secret query values from displayed URLs. The transport re-resolves the hostname at connection time, rejects the entire answer if any address is non-global, and connects directly to a validated IP while retaining the original hostname for HTTP Host/TLS identity. Non-success HTTP responses are not saved as binary artifacts.

**Security limitation:** This remains experimental and is not yet deployment-verified. The DNS-pinning transport relies on a private `httpcore` connection-pool interface and must fail closed if that interface changes; isolated runtime verification is still outstanding. Do not expose arbitrary URL fetch to untrusted remote callers or treat the current checks as complete production SSRF protection. Fetched page text and links are untrusted data, not instructions.

## Persistent Notepad

The desktop quick notepad keeps its local draft and can save a `Quick Note` to the backend using `GET /notepad`, `POST /notepad`, and `PATCH /notepad/{note_id}`. Notes are stored atomically in `memory/notepad.json`, validated on read, bounded to 200 characters for titles and 20,000 for content, and secret-like values are redacted before persistence. Corrupt persisted state is rejected rather than silently reset.

## Feature Control Center

The feature registry contains 28 catalog entries. The backend exposes `GET /features` for the full catalog and dependency/provider blockers, `GET /features/{feature_id}` for readiness, and `POST /features/{feature_id}/activate` / `POST /features/{feature_id}/deactivate` for explicit lifecycle changes. The desktop sidebar includes **Features (28)** to inspect and manage entries. Activation checks dependencies, health, and required provider registration; protected core features cannot be disabled. Invalid optional-provider configuration is isolated per provider: Lumira logs a sanitized warning, leaves that provider unavailable, and keeps the core API running. Registry activation does not provision provider credentials or override the terminal's verified OS-sandbox gate. Features requiring external providers remain unavailable until their providers are configured. See [`docs/feature_completion_matrix.md`](docs/feature_completion_matrix.md) for the source-level inventory of all 28 entries and remaining gates.

## Intelligence status and operating modes

- `GET /intelligence/status` reports registered Brain stages, feature-catalog counts and blockers, configured optional providers, and the current terminal sandbox safety gate.
- `POST /intelligence/analyze` accepts `{ "text": "..." }` and returns deterministic intent, language, and mode analysis without executing the requested action.
- `GET /intelligence/history` returns recent pipeline records, aggregate stats, and optional session/project/success filters.
- `GET /modes` lists the available operating modes. Add `?session_id=...` to include that session's active mode.
- `POST /modes/select` accepts `{ "session_id": "...", "mode_id": "builder" }` and persists the selected mode to an active session. Unknown modes and inactive sessions are rejected.
- The desktop mode selectors now expose all eight registered modes in addition to Auto Category. The settings page displays Brain-stage count, feature count, configured providers, and the terminal safety state.

Language detection recognizes Tamil Unicode and a bounded lexicon of common romanized Tamil terms, including common Tamil-English code-switching patterns. This is language classification only: it does not establish complete Tamil semantic command understanding or guarantee that every transliterated spelling is recognized.

These additions expose existing intelligence components; they do not imply external providers are configured or enable project command execution.

## Tests and checks

**Safety prerequisite:** run project-controlled tests and desktop scripts only inside a disposable Windows Sandbox, with the source mounted read-only and copied into a guest-local writable workspace. Keep networking disabled unless a test specifically requires it. Do not run pytest/npm scripts directly on the host. The generated-project terminal is not a sandbox and remains disabled until it has its own verified per-run isolation provider.

**Recorded results (2026-10-19):** focused recovery/agent tests passed 43 tests in a sandbox. The recorded full backend run completed with 355 passed and 1 failed in an older copied workspace because a nested provider-startup subprocess exceeded the earlier 60-second timeout. The test has since been refactored to exercise provider registration directly in-process, and now includes a malformed optional-provider configuration regression; the full suite has not been rerun. Desktop build and lint passed in an earlier sandbox run; Vitest did not complete because the old harness used an unsupported `--minWorkers` option. The harness now uses `--maxWorkers=1`, but a fresh Vitest result is pending. These historical results do not verify the current worktree.

The following commands are the verification suite to run inside the disposable sandbox:

```bash
pytest
python -m compileall app
npm --prefix lumira_desktop run build
npm --prefix lumira_desktop run lint
npm --prefix lumira_desktop test
```

A syntax-only source inspection does not establish behavioral correctness. The verification gate remains **incomplete** until the full backend suite and desktop Vitest pass on a fresh copy of the current worktree inside the sandbox. Earlier build/lint passes are useful evidence but must also be refreshed after the latest edits. Do not interpret historical test counts as verification of the current working tree.

Sessions, structured cognitive memory, and artifact indexes use atomic local
JSON persistence; generated API records use SQLite. The application is
configured for one local backend worker, not concurrent multi-process or
multi-user deployment. External speech transcription/summarization, rendered
images, image understanding, and web research require configured providers. Missing providers
return explicit unavailable results. Provider protocols are injectable, and
successful transcript, summary, and image results are validated and stored as
artifacts; web research must return bounded findings and source references.
Image understanding is available at `POST /images/analyze` with JSON fields
`image_base64` and optional `prompt`; configure `LUMIRA_VISION_ENABLED=1`,
`LUMIRA_VISION_API_KEY`, and optionally `LUMIRA_VISION_BASE_URL` / `LUMIRA_VISION_MODEL`.
The endpoint accepts PNG, JPEG, or WebP images up to 10 MB and returns a validated
text description; no analysis is fabricated when the provider is unavailable. Set
`save_artifact: true` in the request to save a JSON report through Artifact Manager;
only the prompt, model, description, timestamp, and SHA-256 image fingerprint are
stored—the original image is not saved by this option. Persistence is opt-in, and a
storage failure preserves the successful analysis while returning `artifact_saved: false`.
In PowerShell, configure the provider for the current terminal before starting Lumira:

```powershell
$env:LUMIRA_VISION_ENABLED = "1"
$env:LUMIRA_VISION_API_KEY = "your-provider-key"
# Optional OpenAI-compatible endpoint/model overrides:
# $env:LUMIRA_VISION_BASE_URL = "https://api.openai.com/v1"
# $env:LUMIRA_VISION_MODEL = "gpt-4o-mini"
python run.py
```

Do not commit API keys or put them into chat messages.
Lumira does not fabricate provider output. Generated API templates bound string fields and allow up to 1,000
records per account. Generated authentication uses persistent salted password
hashes and signed bearer tokens, but production deployment still requires
user provisioning, key management, shared rate limiting for multi-worker deployments, and app-specific authorization.

## Optional local wake-word detection

Lumira has an opt-in Picovoice Porcupine adapter and a separate continuous microphone-listener lifecycle. It needs a Picovoice access key and a custom .ppn keyword model generated for Lumira in Picovoice Console. Install both optional audio packages in the same Python environment as the backend:

```powershell
python -m pip install pvporcupine pvrecorder
$env:LUMIRA_WAKE_WORD_ENABLED = "1"
$env:LUMIRA_WAKE_WORD_API_KEY = "set-your-local-access-key"
$env:LUMIRA_WAKE_WORD_MODEL_PATH = "C:/path/to/lumira.ppn"
python run.py
```

The uploaded-recording endpoint accepts only mono, 16-bit PCM WAV files at the detector's sample rate, with a 25 MB file cap and a 60-second processing cap. Continuous listening uses the local microphone through PvRecorder. Once the backend is running, the desktop's **Start Wake Word** and **Stop Wake Word** controls call `POST /voice/wake-word/start` and `POST /voice/wake-word/stop`; `GET /voice/wake-word/status` reports listener state. Starting the listener explicitly opens microphone capture. Detection marks Lumira as activated but does not execute a command or automatically send audio to a cloud service. Credentials and the keyword model are local configuration, not source files. Without the enable flag, access key, existing model file, or optional packages, listening remains unavailable and reports an explicit error.

## Project terminal safety

The generated-project terminal runner is **not an OS sandbox**. Its predefined `pytest` and `npm` commands may execute code from the selected project. Execution is disabled by default. Do not enable it for untrusted projects.

Execution cannot be enabled with an environment variable or UI confirmation. It will remain disabled until genuine OS-level isolation is implemented and verified.

The API returns `project_execution_disabled` while the sandbox status is false. This prevents direct API clients from bypassing the desktop warning. The command list remains available so the desktop can show which checks will eventually be supported.

## Workflow recovery

Workflow checkpoints are persisted in `memory/workflow_runs.json`. Inspect runs with
`GET /recovery/runs` or `GET /recovery/runs/{run_id}`; request a guarded retry with
`POST /recovery/runs/{run_id}/resume`. To create a new checkpointed recovery
run without executing it immediately, use `POST /recovery/runs/{run_id}/window`.
Completed stages are preserved, retries are
bounded, and a stage already marked running cannot be started twice. If a side-effect
stage such as `save_project`, `save_artifact`, or `apply_changes` was interrupted
with an uncertain outcome, Lumira blocks automatic retry and requires manual
reconciliation. Blocked runs cannot be restarted or finalized by changing stage
state directly. Recovery windows are limited to one child per parent, at most three
windows in a chain, and cannot reset an exhausted retry budget.

## Explicit agent delegation

Agent work is available through the primary `/command` route only when you explicitly request delegation. The main Brain pipeline validates the command once, then the bounded agent manager dispatches the task:

- `delegate to agent: Research ESP32 sensor options` — deterministic dispatch to a matching registered agent.
- `delegate to code_agent: Create a small FastAPI task API` — explicitly choose the code agent.
- `delegate to planner_agent: Make a three-step project roadmap` — explicitly choose the planner agent.
- `delegate to research_agent: Compare two microcontroller options` — explicitly choose the research agent.

The command parser does not silently route normal requests to agents. Named-agent requests are checked against the registered agent list, and agent task size, concurrency, and timeout limits remain enforced. This integration does not enable arbitrary shell execution or the disabled generated-project terminal.


## Feature lifecycle commands

The primary /command parser supports explicit feature discovery and lifecycle requests:

- `list features`, `list all features`, `show features` — list registered feature metadata and activation blockers.
- `feature status image generation`, `status of feature voice capture`, `check feature artifact manager` — inspect a feature and whether it can be enabled.
- `activate image generation`, `disable image generation` — request a dependency-checked lifecycle change.

Feature names are resolved case-insensitively; spaces, hyphens, and repeated whitespace are normalized to registry IDs. Selected aliases such as `voice capture` resolve to `voice_idea_capture`. Dependency failures are reported instead of being treated as success. The terminal feature remains blocked until genuine OS-level sandboxing is implemented and verified.
