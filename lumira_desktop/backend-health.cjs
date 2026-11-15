'use strict';

function isLumiraHealthPayload(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return false;
  const services = payload.services;
  const providers = payload.providers;
  return payload.status === 'ok'
    && services !== null
    && typeof services === 'object'
    && services.validate === true
    && services.execute === true
    && services.memory === true
    && providers !== null
    && typeof providers === 'object'
    && !Array.isArray(providers);
}

module.exports = { isLumiraHealthPayload };
