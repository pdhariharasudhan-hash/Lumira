const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const {
  installBackendRuntime,
  prepareWorkspace,
} = require('../backend-runtime.cjs');

function tempDirectory() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'lumira-runtime-'));
}

test('legacy user data migrates without overwriting existing workspace data', () => {
  const root = tempDirectory();
  const legacy = path.join(root, 'backend');
  const workspace = path.join(root, 'workspace');
  fs.mkdirSync(path.join(legacy, 'memory'), { recursive: true });
  fs.mkdirSync(path.join(workspace, 'memory'), { recursive: true });
  fs.writeFileSync(path.join(legacy, 'memory', 'old.json'), 'old');
  fs.writeFileSync(path.join(workspace, 'memory', 'current.json'), 'current');

  prepareWorkspace(root);

  assert.equal(fs.readFileSync(path.join(workspace, 'memory', 'old.json'), 'utf8'), 'old');
  assert.equal(fs.readFileSync(path.join(workspace, 'memory', 'current.json'), 'utf8'), 'current');
});

test('runtime upgrade replaces code while preserving persistent workspace data', () => {
  const root = tempDirectory();
  const bundled = path.join(root, 'bundled');
  const workspace = prepareWorkspace(root);
  fs.mkdirSync(bundled, { recursive: true });
  fs.writeFileSync(path.join(bundled, 'run.py'), 'print("new")');
  fs.writeFileSync(path.join(workspace, 'memory.json'), '{"keep":true}');

  const runtime = installBackendRuntime({
    userData: root,
    bundled,
    appVersion: '1.0.0',
  });

  assert.equal(fs.readFileSync(path.join(runtime, 'run.py'), 'utf8'), 'print("new")');
  assert.equal(fs.readFileSync(path.join(workspace, 'memory.json'), 'utf8'), '{"keep":true}');
  assert.match(fs.readFileSync(path.join(runtime, '.lumira-runtime-version'), 'utf8'), /^1\.0\.0-/);
});
