const { app, BrowserWindow, dialog } = require('electron');
const { spawn, execFile } = require('child_process');
const http = require('http');
const path = require('path');
const fs = require('fs');
const { installBackendRuntime, prepareWorkspace } = require('./backend-runtime.cjs');
const { createApiProxyHandler } = require('./electron-api-proxy.cjs');

const API_PORT = Number(process.env.LUMIRA_API_PORT || 8000);
const APP_PORT = Number(process.env.LUMIRA_APP_PORT || 5000);
const proxyApiRequest = createApiProxyHandler(API_PORT);
let backend = null;
let ownsBackend = false;
let server = null;
let shuttingDown = false;
let backendRecoveryTimer = null;
let backendRecoveryAttempts = 0;

const isPackaged = app.isPackaged;
const logDir = app.getPath('userData');
const logFile = path.join(logDir, 'lumira-desktop.log');

function log(message) {
  try {
    fs.mkdirSync(logDir, { recursive: true });
    fs.appendFileSync(logFile, '[' + new Date().toISOString() + '] ' + message + '\n');
  } catch {}
}

function existing(candidates) {
  return candidates.find(candidate => candidate && fs.existsSync(candidate)) || null;
}

function backendWorkspaceRoot() {
  return prepareWorkspace(app.getPath('userData'), message => log(message));
}

function runtimeBackendRoot() {
  if (!isPackaged) return null;
  try {
    return installBackendRuntime({
      userData: app.getPath('userData'),
      bundled: path.join(process.resourcesPath, 'backend'),
      appVersion: app.getVersion(),
      log: message => log(message),
    });
  } catch (error) {
    log('Backend runtime installation failed: ' + (error.message || String(error)));
    return null;
  }
}
function backendRoot() {
  return existing([
    process.env.LUMIRA_PROJECT_ROOT,
    runtimeBackendRoot(),
    isPackaged ? path.join(process.resourcesPath, 'backend') : null,
    'E:\\Hari\\personal_ai_core'
  ]);
}

function pythonExecutable(root) {
  return existing([
    process.env.LUMIRA_PYTHON,
    isPackaged ? path.join(process.resourcesPath, 'python-runtime', 'Scripts', 'python.exe') : null,
    root ? path.join(root, '.venv', 'Scripts', 'python.exe') : null,
    root ? path.join(root, 'venv', 'Scripts', 'python.exe') : null
  ]);
}

const uiRoot = isPackaged
  ? path.join(app.getAppPath(), 'dist')
  : path.join(__dirname, 'dist');

if (!app.requestSingleInstanceLock()) app.quit();
app.on('second-instance', () => {
  const win = BrowserWindow.getAllWindows().find(window => window.isVisible());
  if (win) { if (win.isMinimized()) win.restore(); win.focus(); }
});

function probe(port, route = '/') {
  return new Promise(resolve => {
    const req = http.get({ host: '127.0.0.1', port, path: route, timeout: 1500 }, res => {
      res.resume();
      resolve(res.statusCode >= 200 && res.statusCode < 300);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

async function waitFor(port, route, timeout = 45000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await probe(port, route)) return true;
    await new Promise(resolve => setTimeout(resolve, 400));
  }
  return false;
}

async function ensureBackend() {
  if (await probe(API_PORT, '/health')) {
    log('Using existing Lumira backend on port ' + API_PORT);
    return;
  }

  const root = backendRoot();
  const python = pythonExecutable(root);
  if (!root || !fs.existsSync(path.join(root, 'run.py'))) {
    throw new Error('Lumira backend files were not found.');
  }
  if (!python) {
    throw new Error('Lumira Python runtime was not found.');
  }

  const workspace = isPackaged ? backendWorkspaceRoot() : root;
  const backendScript = path.join(root, 'run.py');
  const backendEnv = {
    ...process.env,
    HOST: '127.0.0.1',
    PORT: String(API_PORT),
    RELOAD: 'false',
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',
  };
  if (isPackaged) {
    // The desktop shortcut and installer now receive the same local-provider
    // defaults as the development launcher. Explicit user settings still win.
    backendEnv.LUMIRA_OLLAMA_BASE_URL ||= 'http://127.0.0.1:11434/v1';
    backendEnv.LUMIRA_OLLAMA_SUMMARY_ENABLED ||= 'true';
    backendEnv.LUMIRA_OLLAMA_VISION_ENABLED ||= 'true';
    backendEnv.LUMIRA_OLLAMA_VISION_MODEL ||= 'moondream';
    backendEnv.LUMIRA_WINDOWS_SAPI_TTS_ENABLED ||= 'true';
    backendEnv.LUMIRA_LOCAL_TRANSCRIPTION_ENABLED ||= 'true';
    backendEnv.LUMIRA_LOCAL_TRANSCRIPTION_MODEL ||= 'base';
    backendEnv.LUMIRA_LOCAL_TRANSCRIPTION_COMPUTE_TYPE ||= 'int8';
  }

  log('Starting backend code from ' + root + ' with persistent workspace ' + workspace);
  backend = spawn(python, [backendScript], {
    cwd: workspace,
    windowsHide: true,
    env: backendEnv,
    stdio: ['ignore', 'pipe', 'pipe']
  });
  ownsBackend = true;
  backend.stdout?.on('data', data => log('Backend: ' + String(data).trim()));
  backend.stderr?.on('data', data => log('Backend error: ' + String(data).trim()));
  backend.once('error', error => log('Backend process error: ' + error.message));
  backend.once('exit', (code, signal) => {
    log('Backend exited: code=' + code + ' signal=' + signal);
    if (!shuttingDown) scheduleBackendRecovery();
  });

  if (!(await waitFor(API_PORT, '/health'))) {
    throw new Error('Lumira services did not become ready. Diagnostic log: ' + logFile);
  }
  log('Lumira backend is ready');
}

function scheduleBackendRecovery() {
  if (shuttingDown || backendRecoveryTimer) return;
  const delay = Math.min(30000, 2000 * Math.max(1, 2 ** backendRecoveryAttempts));
  backendRecoveryTimer = setTimeout(async () => {
    backendRecoveryTimer = null;
    try {
      log('Attempting backend recovery, attempt ' + (backendRecoveryAttempts + 1));
      await ensureBackend();
      backendRecoveryAttempts = 0;
      log('Backend recovery succeeded');
    } catch (error) {
      backendRecoveryAttempts += 1;
      log('Backend recovery failed: ' + (error.message || String(error)));
      scheduleBackendRecovery();
    }
  }, delay);
}

function mime(file) {
  const ext = path.extname(file).toLowerCase();
  return ({'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.ico':'image/x-icon','.woff2':'font/woff2'})[ext] || 'application/octet-stream';
}

function startServer() {
  if (server) return Promise.resolve();
  if (!fs.existsSync(path.join(uiRoot, 'index.html'))) throw new Error('Lumira interface files are missing.');

  server = http.createServer((req, res) => {
    const url = new URL(req.url || '/', 'http://127.0.0.1');
    if (proxyApiRequest(req, res)) return;

    let requested = '/index.html';
    try { if (url.pathname !== '/') requested = decodeURIComponent(url.pathname); } catch {}
    const root = path.resolve(uiRoot);
    let target = path.resolve(root, '.' + requested);
    if (!target.startsWith(root + path.sep) || !fs.existsSync(target) || fs.statSync(target).isDirectory()) target = path.join(root, 'index.html');

    fs.readFile(target, (error, data) => {
      if (error) { res.writeHead(500); res.end('Lumira interface unavailable.'); return; }
      res.writeHead(200, {'Content-Type': mime(target), 'Cache-Control':'no-cache'});
      res.end(data);
    });
  });

  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(APP_PORT, '127.0.0.1', () => {
      server.off('error', reject);
      resolve();
    });
  });
}

function createSplash() {
  const splash = new BrowserWindow({
    width: 480, height: 300, frame: false, transparent: false,
    resizable: false, movable: true, alwaysOnTop: true, center: true,
    backgroundColor: '#030812',
    webPreferences: { contextIsolation: true, nodeIntegration: false }
  });
  const html = '<!doctype html><html><body style="margin:0;background:#030812;color:#eef4ff;font-family:Segoe UI,Arial;display:flex;align-items:center;justify-content:center;height:100vh"><div style="text-align:center"><div style="font-size:44px;font-weight:700;letter-spacing:2px">LUMIRA</div><div style="margin-top:20px;color:#9fb2d0;font-size:15px">Starting your personal AI...</div><div style="margin:28px auto 0;width:220px;height:3px;background:#16233a;border-radius:4px;overflow:hidden"><div style="width:45%;height:100%;background:#7ea7ff;animation:l 1.2s infinite alternate"></div></div></div><style>@keyframes l{to{transform:translateX(120px)}}</style></body></html>';
  splash.loadURL('data:text/html;charset=UTF-8,' + encodeURIComponent(html));
  return splash;
}

async function launch() {
  const splash = createSplash();
  let win = null;
  try {
    await ensureBackend();
    await startServer();

    win = new BrowserWindow({
      width: 1440, height: 900, minWidth: 1000, minHeight: 700,
      title: 'Lumira', autoHideMenuBar: true, backgroundColor: '#030812', show: false,
      webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true }
    });
    win.once('ready-to-show', () => {
      if (!win.isDestroyed()) win.show();
      if (!splash.isDestroyed()) splash.close();
    });
    await win.loadURL('http://127.0.0.1:' + APP_PORT);
  } catch (error) {
    log('Startup failure: ' + (error.stack || error.message || String(error)));
    if (win && !win.isDestroyed()) win.destroy();
    if (!splash.isDestroyed()) splash.close();
    dialog.showErrorBox('Lumira could not start', (error.message || String(error)) + '\n\nLumira saved startup details to:\n' + logFile);
    app.quit();
  }
}

function stop(child) {
  if (!child || child.killed) return;
  if (process.platform === 'win32') execFile('taskkill', ['/pid', String(child.pid), '/t', '/f'], () => {});
  else child.kill('SIGTERM');
}

app.whenReady().then(launch);
app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => {
  shuttingDown = true;
  if (backendRecoveryTimer) clearTimeout(backendRecoveryTimer);
  if (server) server.close();
  if (ownsBackend) stop(backend);
});