# Lumira

Lumira is a modular personal AI core with a FastAPI backend and a separate
React/Vite desktop workbench. The Handoff 12 Brain/Command flow is the
authoritative application path.

## Run the backend

From the repository root:

```bash
pip install -r requirements.txt
python run.py
```

The backend listens on port `8000` by default. `HOST`, `PORT`, and `RELOAD`
can be set through environment variables. The FastAPI application is
`app.main:app`; the root `main.py` is an unrelated legacy sample.

## Run the desktop workbench

In a second terminal:

```bash
npm ci --prefix lumira_desktop
npm --prefix lumira_desktop run dev -- --host 0.0.0.0 --port 5000
```

The Vite development server proxies the Brain, Command, session, memory, and
health requests to the backend on port `8000`.

## Tests and checks

```bash
pytest
python -m compileall app
npm --prefix lumira_desktop run build
npm --prefix lumira_desktop run lint
```

The repository uses local JSON persistence and is intended for a single
backend worker. External transcription, summarization, and image-rendering
providers are optional and report an explicit unavailable-provider response
when not configured.
