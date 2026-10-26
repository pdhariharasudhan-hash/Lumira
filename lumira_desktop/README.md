# Lumira Desktop Workbench

The desktop workbench is a React, TypeScript, and Vite interface for the local Lumira FastAPI backend.

## Start

From the repository root, start the backend first:

```powershell
python run.py
```

In a second terminal, start the desktop development server:

```powershell
npm --prefix lumira_desktop run dev -- --host 127.0.0.1 --port 5000
```

Open `http://127.0.0.1:5000`. Vite proxies the desktop API roots to `http://127.0.0.1:8000`; keep both services on loopback. Do not expose the Vite proxy to a LAN by overriding the host with `0.0.0.0`.

## Available scripts

- `npm --prefix lumira_desktop run dev` — local development server.
- `npm --prefix lumira_desktop run test` — Vitest regression suite.
- `npm --prefix lumira_desktop run build` — TypeScript project build and Vite production bundle.
- `npm --prefix lumira_desktop run lint` — Oxlint.

Behavioral tests, build, and lint have not been re-run in the current work session because verified OS-level isolation is unavailable. Do not treat static parser checks as a replacement for those checks.

See the repository-root `README.md` for backend setup, optional provider configuration, and security notes.
