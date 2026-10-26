import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { ProviderDiagnosticsPanel } from "../components/Common/ProviderDiagnosticsPanel";

vi.mock("../api/client", () => ({ api: { providerStatus: vi.fn() } }));

afterEach(() => cleanup());
beforeEach(() => vi.clearAllMocks());

describe("ProviderDiagnosticsPanel", () => {
  it("shows registration state, local model metadata, and configuration blockers", async () => {
    vi.mocked(api.providerStatus).mockResolvedValue({
      registered_count: 1,
      configured_but_unregistered: ["transcription"],
      providers: {
        image_understanding: {
          registered: true,
          configured: true,
          availability: "registered",
          implementation: "OllamaVisionProvider",
          execution_mode: "local",
          model: "moondream",
        },
        transcription: {
          registered: false,
          configured: true,
          availability: "not_registered",
        },
      },
    });

    render(<ProviderDiagnosticsPanel />);
    expect(await screen.findByText("image understanding")).toBeTruthy();
    expect(screen.getByText("OllamaVisionProvider")).toBeTruthy();
    expect(screen.getByText(/Model: moondream · Mode: local/)).toBeTruthy();
    expect(screen.getByText(/Enabled but not registered: transcription/)).toBeTruthy();
    expect(screen.getByText("Enabled, not registered")).toBeTruthy();
  });

  it("allows a user-triggered refresh and reports provider API errors", async () => {
    vi.mocked(api.providerStatus)
      .mockResolvedValueOnce({ providers: {} })
      .mockRejectedValueOnce(new Error("Backend unavailable"));

    render(<ProviderDiagnosticsPanel />);
    expect(await screen.findByText("0 registered")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Refresh providers" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("Backend unavailable");
    expect(api.providerStatus).toHaveBeenCalledTimes(2);
  });
});
