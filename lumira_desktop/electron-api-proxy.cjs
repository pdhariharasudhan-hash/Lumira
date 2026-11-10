'use strict';

const http = require('http');

const API_ROOTS = new Set([
  'brain', 'command', 'health', 'ai-mode', 'intelligence', 'images',
  'modes', 'features', 'notepad', 'sessions', 'memory', 'projects',
  'artifacts', 'goals', 'workflows', 'search', 'runs', 'voice',
  'devices', 'providers', 'resources', 'openapi.json',
]);

function createApiProxyHandler(apiPort) {
  return function proxyApiRequest(req, res) {
    const url = new URL(req.url || '/', 'http://127.0.0.1');
    const first = url.pathname.split('/').filter(Boolean)[0] || '';
    if (!API_ROOTS.has(first)) return false;

    const upstream = http.request({
      host: '127.0.0.1',
      port: apiPort,
      method: req.method,
      path: url.pathname + url.search,
      headers: { ...req.headers, host: '127.0.0.1:' + apiPort },
    }, response => {
      res.writeHead(response.statusCode || 502, response.headers);
      response.pipe(res);
    });

    upstream.on('error', () => {
      if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ detail: 'Lumira service unavailable.' }));
    });

    req.pipe(upstream);
    return true;
  };
}

module.exports = { API_ROOTS, createApiProxyHandler };
