'use strict';

const assert = require('node:assert/strict');
const http = require('node:http');
const { test } = require('node:test');
const { createApiProxyHandler } = require('./electron-api-proxy.cjs');

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

function request(port, path, method = 'GET', body = '') {
  return new Promise((resolve, reject) => {
    const req = http.request({
      host: '127.0.0.1',
      port,
      path,
      method,
      headers: body ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } : {},
    }, res => {
      const chunks = [];
      res.on('data', chunk => chunks.push(chunk));
      res.on('end', () => resolve({
        status: res.statusCode,
        body: Buffer.concat(chunks).toString('utf8'),
      }));
    });
    req.on('error', reject);
    req.end(body);
  });
}

test('Electron proxy forwards AI settings GET requests and query strings', async () => {
  let received;
  const backend = http.createServer((req, res) => {
    received = { method: req.method, url: req.url, host: req.headers.host };
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ success: true, mode: 'offline', cloud_enabled: false }));
  });
  const backendPort = await listen(backend);
  const proxy = http.createServer((req, res) => {
    if (!createApiProxyHandler(backendPort)(req, res)) {
      res.writeHead(404);
      res.end();
    }
  });
  const proxyPort = await listen(proxy);

  try {
    const response = await request(proxyPort, '/ai-mode?source=settings');
    assert.equal(response.status, 200);
    assert.deepEqual(JSON.parse(response.body), {
      success: true, mode: 'offline', cloud_enabled: false,
    });
    assert.deepEqual(received, {
      method: 'GET',
      url: '/ai-mode?source=settings',
      host: '127.0.0.1:' + backendPort,
    });
  } finally {
    await close(proxy);
    await close(backend);
  }
});

test('Electron proxy forwards cloud-permission POST bodies unchanged', async () => {
  let receivedBody = '';
  const backend = http.createServer((req, res) => {
    req.setEncoding('utf8');
    req.on('data', chunk => { receivedBody += chunk; });
    req.on('end', () => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(receivedBody);
    });
  });
  const backendPort = await listen(backend);
  const proxy = http.createServer((req, res) => {
    if (!createApiProxyHandler(backendPort)(req, res)) {
      res.writeHead(404);
      res.end();
    }
  });
  const proxyPort = await listen(proxy);
  const payload = JSON.stringify({ cloud_enabled: true });

  try {
    const response = await request(proxyPort, '/ai-mode/cloud', 'PUT', payload);
    assert.equal(response.status, 200);
    assert.equal(receivedBody, payload);
    assert.equal(response.body, payload);
  } finally {
    await close(proxy);
    await close(backend);
  }
});

test('Electron proxy returns a bounded 502 response when the backend is unavailable', async () => {
  const backend = http.createServer();
  const backendPort = await listen(backend);
  await close(backend);

  const proxy = http.createServer((req, res) => {
    if (!createApiProxyHandler(backendPort)(req, res)) {
      res.writeHead(404);
      res.end();
    }
  });
  const proxyPort = await listen(proxy);

  try {
    const response = await request(proxyPort, '/ai-mode');
    assert.equal(response.status, 502);
    assert.deepEqual(JSON.parse(response.body), { detail: 'Lumira service unavailable.' });
  } finally {
    await close(proxy);
  }
});
