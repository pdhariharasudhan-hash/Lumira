'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { isLumiraHealthPayload } = require('../backend-health.cjs');

test('accepts the current Lumira health contract', () => {
  assert.equal(isLumiraHealthPayload({
    status: 'ok',
    services: { validate: true, builder: true, execute: true, code: true, memory: true },
    providers: { transcription: { registered: false } },
    missing_optional_providers: ['transcription'],
    security: { project_terminal_execution: 'disabled', sandbox_verification: 'not_implemented' },
  }), true);
});

test('rejects generic 200 responses and incomplete health contracts', () => {
  assert.equal(isLumiraHealthPayload({ status: 'ok' }), false);
  assert.equal(isLumiraHealthPayload({ status: 'healthy', services: { validate: true, execute: true, memory: true }, providers: {} }), false);
  assert.equal(isLumiraHealthPayload({ status: 'ok', services: { validate: true, execute: true, memory: false }, providers: {} }), false);
  assert.equal(isLumiraHealthPayload({ status: 'ok', services: { validate: true, execute: true, memory: true }, providers: [] }), false);
  assert.equal(isLumiraHealthPayload(null), false);
  assert.equal(isLumiraHealthPayload('ok'), false);
});


test('packaged Electron files include the health identity helper and API proxy', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const packageJson = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'package.json'),
    'utf8',
  ));
  const files = packageJson.build.files;
  assert.equal(files.includes('backend-health.cjs'), true);
  assert.equal(files.includes('electron-api-proxy.cjs'), true);
  assert.equal(files.includes('electron-main.cjs'), true);
});
