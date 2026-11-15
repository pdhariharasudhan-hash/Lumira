'use strict';

const http = require('http');

const API_ROOTS = new Set([
  'agents', 'ai-mode', 'artifacts', 'background-tasks', 'brain', 'command',
  'creator', 'data', 'device-profiles', 'devices', 'features', 'goals',
  'health', 'images', 'intelligence', 'market', 'memory', 'modes', 'notepad',
  'openapi.json', 'projects', 'providers', 'resources', 'runs', 'search',
  'sessions', 'system', 'voice', 'workflows',
]);

const ALLOWED_METHODS = new Set(['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']);
const HOP_BY_HOP_HEADERS = new Set([
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'proxy-connection', 'te', 'trailer', 'transfer-encoding', 'upgrade',
]);

function withoutHopByHopHeaders(headers) {
  const clean = {};
  for (const [name, value] of Object.entries(headers || {})) {
    if (!HOP_BY_HOP_HEADERS.has(name.toLowerCase()) && name.toLowerCase() !== 'host') {
      clean[name] = value;
    }
  }
  return clean;
}

function sendJson(res, status, payload) {
  if (res.headersSent) return;
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(payload));
}

function createApiProxyHandler(apiPort) {
  if (!Number.isInteger(apiPort) || apiPort < 1 || apiPort > 65535) {
    throw new RangeError('API port must be an integer between 1 and 65535');
  }

  return function proxyApiRequest(req, res) {
    let url;
    try {
      url = new URL(req.url || '/', 'http://127.0.0.1');
    } catch {
      sendJson(res, 400, { detail: 'Invalid API request path.' });
      return true;
    }

    if (url.origin !== 'http://127.0.0.1' || !url.pathname.startsWith('/')) {
      sendJson(res, 400, { detail: 'Invalid API request target.' });
      return true;
    }

    const first = url.pathname.split('/').filter(Boolean)[0] || '';
    if (!API_ROOTS.has(first)) return false;

    const method = String(req.method || 'GET').toUpperCase();
    if (!ALLOWED_METHODS.has(method)) {
      sendJson(res, 405, { detail: 'HTTP method is not supported by the desktop API proxy.' });
      return true;
    }

    const headers = withoutHopByHopHeaders(req.headers);
    headers.host = '127.0.0.1:' + apiPort;

    const upstream = http.request({
      host: '127.0.0.1',
      port: apiPort,
      method,
      path: url.pathname + url.search,
      headers,
    }, response => {
      res.writeHead(response.statusCode || 502, withoutHopByHopHeaders(response.headers));
      response.pipe(res);
    });

    upstream.setTimeout(120000, () => {
      upstream.destroy(new Error('upstream_timeout'));
    });
    upstream.on('error', error => {
      if (!res.headersSent) {
        sendJson(res, error.message === 'upstream_timeout' ? 504 : 502, {
          detail: error.message === 'upstream_timeout'
            ? 'Lumira service request timed out.'
            : 'Lumira service unavailable.',
        });
      } else if (!res.writableEnded) {
        res.destroy();
      }
    });

    req.pipe(upstream);
    return true;
  };
}

module.exports = { API_ROOTS, createApiProxyHandler };
