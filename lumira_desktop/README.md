# Lumira Desktop Application

Lumira is a packaged Windows desktop application for the local Lumira Personal AI system. The installed application starts and manages its own local backend; normal use does not require opening a terminal or running `npm run dev`.

## Installed application

Install the Windows package from the `release` output. Launch **Lumira** from the Start menu or desktop shortcut. The splash screen waits for the local services to become healthy before opening the workspace.

If the backend stops unexpectedly while Lumira is open, the desktop host attempts to restart it automatically. Startup and recovery diagnostics are written to the Lumira user-data folder as `lumira-desktop.log`.

## Development

Development still uses separate backend and Vite processes:

```powershell
# repository root
python run.py

# another terminal
npm --prefix lumira_desktop run dev
```

## Quality checks

```powershell
npm --prefix lumira_desktop run test
npm --prefix lumira_desktop run lint
npm --prefix lumira_desktop run build
node --check lumira_desktop/electron-main.cjs
```

## Packaging

```powershell
npm --prefix lumira_desktop run dist
```

The packaged build bundles the production interface, Lumira backend files, and the configured Python runtime. Optional AI providers remain optional: when a provider is not configured, Lumira reports that state instead of pretending the feature is available.

See the repository-root documentation for backend architecture and provider configuration.