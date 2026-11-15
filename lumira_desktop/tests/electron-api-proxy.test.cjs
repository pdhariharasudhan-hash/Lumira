'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { API_ROOTS, createApiProxyHandler } = require('../electron-api-proxy.cjs');

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      server.off('error', reject);
      resolve(server.address().port);
    });
  });
}

function close(server) {
  return new Promise(resolve => server.close(() => resolve()));
}

function request(port, options = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request({
      host: '127.0.0.1',
      port,
      path: options.path || '/',
      method: options.method || 'GET',
      headers: options.headers || {},
    }, response => {
      const chunks = [];
      response.on('data', chunk => chunks.push(chunk));
      response.on('end', () => resolve({
        status: response.statusCode,
        headers: response.headers,
        body: Buffer.concat(chunks).toString('utf8'),
      }));
    });
    req.on('error', reject);
    if (options.body) req.write(options.body);
    req.end();
  });
}

test('API allowlist covers every root used by the desktop API client', () => {
  const expected = [
    'agents', 'ai-mode', 'artifacts', 'background-tasks', 'brain', 'command',
    'creator', 'data', 'device-profiles', 'devices', 'features', 'goals',
    'health', 'images', 'intelligence', 'market', 'memory', 'modes', 'notepad',
    'openapi.json', 'projects', 'providers', 'resources', 'runs', 'search',
    'sessions', 'system', 'voice', 'workflows',
  ];
  for (const root of expected) assert.equal(API_ROOTS.has(root), true, root);
});

test('forwards allowlisted API requests, body, query and safe headers', async () => {
  let received;
  const upstream = http.createServer((req, res) => {
    const chunks = [];
    req.on('data', chunk => chunks.push(chunk));
    req.on('end', () => {
      received = {
        method: req.method,
        url: req.url,
        body: Buffer.concat(chunks).toString('utf8'),
        ownerHeader: req.headers['x-lumira-test'],
        host: req.headers.host,
      };
      res.writeHead(201, { 'Content-Type': 'application/json', 'X-Upstream': 'ok' });
      res.end(JSON.stringify({ accepted: true }));
    });
  });
  const upstreamPort = await listen(upstream);
  const desktop = http.createServer((req, res) => {
    if (!createApiProxyHandler(upstreamPort)(req, res)) {
      res.writeHead(404);
      res.end('not found');
    }
  });
  const desktopPort = await listen(desktop);
  try {
    const response = await request(desktopPort, {
      path: '/market/watchlist?exchange=NSE',
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Lumira-Test': 'proxy-test' },
      body: JSON.stringify({ symbol: 'INFY' }),
    });
    assert.equal(response.status, 201);
    assert.deepEqual(JSON.parse(response.body), { accepted: true });
    assert.equal(response.headers['x-upstream'], 'ok');
    assert.deepEqual(received, {
      method: 'POST',
      url: '/market/watchlist?exchange=NSE',
      body: JSON.stringify({ symbol: 'INFY' }),
      ownerHeader: 'proxy-test',
      host: '127.0.0.1:' + upstreamPort,
    });
  } finally {
    await close(desktop);
    await close(upstream);
  }
});

test('does not forward paths outside the API allowlist', async () => {
  let upstreamHits = 0;
  const upstream = http.createServer((_req, res) => {
    upstreamHits += 1;
    res.end('unexpected');
  });
  const upstreamPort = await listen(upstream);
  const desktop = http.createServer((req, res) => {
    if (!createApiProxyHandler(upstreamPort)(req, res)) {
      res.writeHead(404);
      res.end('not found');
    }
  });
  const desktopPort = await listen(desktop);
  try {
    const response = await request(desktopPort, { path: '/arbitrary/path' });
    assert.equal(response.status, 404);
    assert.equal(upstreamHits, 0);
  } finally {
    await close(desktop);
    await close(upstream);
  }
});

test('rejects unsupported HTTP methods before contacting the backend', async () => {
  let upstreamHits = 0;
  const upstream = http.createServer((_req, res) => {
    upstreamHits += 1;
    res.end('unexpected');
  });
  const upstreamPort = await listen(upstream);
  const desktop = http.createServer((req, res) => createApiProxyHandler(upstreamPort)(req, res));
  const desktopPort = await listen(desktop);
  try {
    const response = await request(desktopPort, { path: '/brain', method: 'TRACE' });
    assert.equal(response.status, 405);
    assert.match(JSON.parse(response.body).detail, /not supported/i);
    assert.equal(upstreamHits, 0);
  } finally {
    await close(desktop);
    await close(upstream);
  }
});

test('returns a sanitized 502 when the backend is unavailable', async () => {
  const unavailable = http.createServer();
  const port = await listen(unavailable);
  await close(unavailable);
  const desktop = http.createServer((req, res) => createApiProxyHandler(port)(req, res));
  const desktopPort = await listen(desktop);
  try {
    const response = await request(desktopPort, { path: '/health' });
    assert.equal(response.status, 502);
    assert.deepEqual(JSON.parse(response.body), { detail: 'Lumira service unavailable.' });
  } finally {
    await close(desktop);
  }
});

test('rejects invalid upstream ports at configuration time', () => {
  assert.throws(() => createApiProxyHandler(0), RangeError);
  assert.throws(() => createApiProxyHandler(65536), RangeError);
  assert.throws(() => createApiProxyHandler(Number.NaN), RangeError);
});


test('rejects absolute-form requests targeting a non-loopback origin', () => {
  const handler = createApiProxyHandler(8000);
  const response = {
    status: null,
    body: '',
    headers: null,
    headersSent: false,
    writeHead(status, headers) { this.status = status; this.headers = headers; },
    end(body) { this.body = body; this.headersSent = true; },
  };
  const handled = handler({ url: 'http://example.com/brain', method: 'GET', headers: {} }, response);
  assert.equal(handled, true);
  assert.equal(response.status, 400);
  assert.deepEqual(JSON.parse(response.body), { detail: 'Invalid API request target.' });
});


test('every literal API route root in the desktop client is allowlisted', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const clientPath = path.join(__dirname, '..', 'src', 'api', 'client.ts');
  const source = fs.readFileSync(clientPath, 'utf8');
  const roots = new Set();
  const routePattern = /[`"']\/([A-Za-z0-9._-]+)/g;
  for (const match of source.matchAll(routePattern)) roots.add(match[1]);
  for (const root of roots) assert.equal(API_ROOTS.has(root), true, 'missing API root: ' + root);
});
