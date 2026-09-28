# Lumira

Lumira is a local personal AI core with a FastAPI backend and a separate
React/Vite desktop workbench. `/command` runs the cognitive Brain first, then
routes the request through mode and capability policy. Project generation
uses validate → builder → execution plan → code generation → source validation
→ versioned save. Failed or incomplete stages stop the pipeline; generated
projects are not reported as complete until their files validate and save.

## Run the backend

From the repository root:

```bash
pip install -r requirements.txt
python run.py
```

The backend listens on `127.0.0.1:8000` by default. `PORT` and `RELOAD` can
be set through environment variables. `HOST` can be set explicitly when
needed; the API has no multi-user authentication and should stay on a trusted
local interface. The FastAPI application is `app.main:app`; the root `main.py`
is an unrelated legacy sample.

## Run the desktop workbench

In a second terminal:

```bash
npm ci --prefix lumira_desktop
npm --prefix lumira_desktop run dev -- --host 0.0.0.0 --port 5000
```

The Vite development server proxies Brain, Command, session, memory, project,
artifact, search, and health requests to the backend on port `8000`.

## Tests and checks

```bash
pytest
python -m compileall app
npm --prefix lumira_desktop run build
npm --prefix lumira_desktop run lint
npm --prefix lumira_desktop test
```

Sessions, structured cognitive memory, and artifact indexes use atomic local
JSON persistence; generated API records use SQLite. The application is
configured for one local backend worker, not concurrent multi-process or
multi-user deployment. External speech transcription/summarization, rendered
images, and web research require configured providers. Missing providers
return explicit unavailable results. Provider protocols are injectable, and
successful transcript, summary, and image results are validated and stored as
artifacts; web research must return bounded findings and source references.
Lumira does not fabricate provider output. Generated API templates bound string fields and allow up to 1,000
records per account. Generated authentication uses persistent salted password
hashes and signed bearer tokens, but production deployment still requires
user provisioning, key management, throttling, and app-specific authorization.
