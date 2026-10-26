import { useEffect, useState } from "react";
import { api } from "../../api/client";

type ProviderState = {
  registered: boolean;
  configured: boolean;
  availability?: string;
  implementation?: string;
  execution_mode?: string;
  model?: string;
};

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function providerState(value: unknown): ProviderState {
  const item = record(value);
  return {
    registered: item.registered === true,
    configured: item.configured === true,
    availability: typeof item.availability === "string" ? item.availability : undefined,
    implementation: typeof item.implementation === "string" ? item.implementation : undefined,
    execution_mode: typeof item.execution_mode === "string" ? item.execution_mode : undefined,
    model: typeof item.model === "string" ? item.model : undefined,
  };
}

export function ProviderDiagnosticsPanel() {
  const [providers, setProviders] = useState<Record<string, ProviderState>>({});
  const [configuredButUnregistered, setConfiguredButUnregistered] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const response = await api.providerStatus();
      const rawProviders = record(response.providers);
      const normalized: Record<string, ProviderState> = {};
      for (const [name, value] of Object.entries(rawProviders)) normalized[name] = providerState(value);
      setProviders(normalized);
      setConfiguredButUnregistered(Array.isArray(response.configured_but_unregistered)
        ? response.configured_but_unregistered.filter((item): item is string => typeof item === "string")
        : []);
      setLoaded(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Provider diagnostics could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  const names = Object.keys(providers).sort((left, right) => left.localeCompare(right));
  const registeredCount = names.filter((name) => providers[name].registered).length;

  return (
    <section className="settings-capability-status" aria-labelledby="provider-diagnostics-title">
      <div className="workspace-page-heading">
        <div>
          <h3 id="provider-diagnostics-title">Provider diagnostics</h3>
          <p>Registration and configuration only. This check does not download models or contact external providers.</p>
        </div>
        <button className="secondary-action" type="button" disabled={loading} onClick={() => void refresh()}>
          {loading ? "Checking…" : "Refresh providers"}
        </button>
      </div>
      {error && <p role="alert">Provider status failed: {error}</p>}
      {!loaded && loading && <p role="status">Loading provider configuration…</p>}
      {loaded && <>
        <div className="metric-strip">
          <span>{registeredCount} registered</span>
          <span>{names.length - registeredCount} not registered</span>
          <span>{configuredButUnregistered.length} configuration issue(s)</span>
        </div>
        {configuredButUnregistered.length > 0 && <p role="status">Enabled but not registered: {configuredButUnregistered.join(", ")}. Check provider credentials, optional dependencies, and local setup.</p>}
        <div className="entity-list">
          {names.map((name) => {
            const provider = providers[name];
            const state = provider.registered ? "Registered" : provider.configured ? "Enabled, not registered" : "Not configured";
            return <article className="entity-row" key={name}>
              <div className="entity-copy">
                <strong>{name.replaceAll("_", " ")}</strong>
                <span>{provider.implementation ?? "No provider implementation registered"}</span>
                <small>{provider.model ? `Model: ${provider.model} · ` : ""}{provider.execution_mode ? `Mode: ${provider.execution_mode.replaceAll("_", "/")}` : "Mode not reported"} · State: {provider.availability ?? "not checked"}</small>
              </div>
              <span className="status-pill">{state}</span>
            </article>;
          })}
        </div>
      </>}
    </section>
  );
}
