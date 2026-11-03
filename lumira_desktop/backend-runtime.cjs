'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const USER_DATA_ENTRIES = [
  'memory', 'artifacts', 'data', '.lumira_data', 'generated',
  'generated_projects', 'projects', 'app.db', 'project_memory.json',
];
const EXCLUDED_BACKEND_ENTRIES = new Set([
  '.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache',
  '.pytest-work', 'tests', 'memory', 'artifacts', 'data', '.lumira_data',
  'generated', 'autodev_review', '.agents',
]);

function copyMissingTree(source, destination) {
  fs.mkdirSync(destination, { recursive: true });
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    const from = path.join(source, entry.name);
    const to = path.join(destination, entry.name);
    if (!fs.existsSync(to)) {
      fs.cpSync(from, to, { recursive: true, errorOnExist: true, force: false });
    } else if (entry.isDirectory() && fs.statSync(to).isDirectory()) {
      copyMissingTree(from, to);
    }
  }
}

function prepareWorkspace(userData, log = () => {}) {
  const workspace = path.join(userData, 'workspace');
  const legacy = path.join(userData, 'backend');

  if (fs.existsSync(legacy)) {
    if (!fs.existsSync(workspace)) {
      // The old release stored application code and user data together.
      // Move the complete directory so no user-owned files are discarded.
      fs.renameSync(legacy, workspace);
      log('Migrated legacy backend directory to persistent workspace');
    } else {
      // Recover a partial migration by copying only missing user data.
      // Existing workspace files always win; the legacy source is retained.
      for (const name of USER_DATA_ENTRIES) {
        const from = path.join(legacy, name);
        const to = path.join(workspace, name);
        if (!fs.existsSync(from)) continue;
        if (!fs.existsSync(to)) {
          fs.cpSync(from, to, { recursive: true, errorOnExist: true, force: false });
        } else if (fs.statSync(from).isDirectory() && fs.statSync(to).isDirectory()) {
          copyMissingTree(from, to);
        }
      }
      log('Checked legacy user-data migration without overwriting existing files');
    }
  }

  fs.mkdirSync(workspace, { recursive: true });
  return workspace;
}

function backendFingerprint(root) {
  const hash = crypto.createHash('sha256');
  const visit = (directory, relative = '') => {
    const entries = fs.readdirSync(directory, { withFileTypes: true })
      .sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      const nextRelative = path.join(relative, entry.name);
      if (!relative && EXCLUDED_BACKEND_ENTRIES.has(entry.name)) continue;
      const absolute = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        visit(absolute, nextRelative);
      } else if (entry.isFile()) {
        hash.update(nextRelative.split(path.sep).join('/'));
        hash.update(fs.readFileSync(absolute));
      }
    }
  };
  visit(root);
  return hash.digest('hex');
}

function installBackendRuntime({ userData, bundled, appVersion, log = () => {} }) {
  prepareWorkspace(userData, log);
  if (!fs.existsSync(path.join(bundled, 'run.py'))) {
    throw new Error('Bundled backend is missing run.py.');
  }

  const runtime = path.join(userData, 'backend-runtime');
  const marker = path.join(runtime, '.lumira-runtime-version');
  const stage = path.join(userData, 'backend-runtime.stage-' + process.pid);
  const version = appVersion + '-' + backendFingerprint(bundled);
  const installedVersion = fs.existsSync(marker)
    ? fs.readFileSync(marker, 'utf8').trim()
    : '';

  if (installedVersion === version && fs.existsSync(path.join(runtime, 'run.py'))) {
    return runtime;
  }

  // Prepare the replacement separately; a failed copy never damages the
  // currently installed runtime or the persistent workspace.
  fs.rmSync(stage, { recursive: true, force: true });
  try {
    fs.cpSync(bundled, stage, {
      recursive: true,
      filter: source => {
        const relative = path.relative(bundled, source);
        const first = relative.split(path.sep)[0];
        return !first || !EXCLUDED_BACKEND_ENTRIES.has(first);
      },
    });
    fs.writeFileSync(path.join(stage, '.lumira-runtime-version'), version);

    let previous = null;
    if (fs.existsSync(runtime)) {
      previous = path.join(userData, 'backend-runtime.previous-' + Date.now());
      fs.renameSync(runtime, previous);
    }
    try {
      fs.renameSync(stage, runtime);
    } catch (installError) {
      if (previous && fs.existsSync(previous) && !fs.existsSync(runtime)) {
        fs.renameSync(previous, runtime);
      }
      throw installError;
    }

    log('Installed backend code version ' + version + '; persistent data remains in workspace');
    return runtime;
  } catch (error) {
    fs.rmSync(stage, { recursive: true, force: true });
    throw error;
  }
}

module.exports = { backendFingerprint, installBackendRuntime, prepareWorkspace };
