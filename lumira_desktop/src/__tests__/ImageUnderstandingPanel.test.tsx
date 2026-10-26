import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { ImageUnderstandingPanel } from "../components/ImageUnderstanding/ImageUnderstandingPanel";

vi.mock("../api/client", () => ({
  api: { analyzeImage: vi.fn(), createBinaryArtifact: vi.fn(), createArtifact: vi.fn() },
}));

function pngFile() {
  return new File([new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10, 1, 2, 3])], "board.png", { type: "image/png" });
}

describe("ImageUnderstandingPanel", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it("submits a selected image and displays the provider description", async () => {
    vi.mocked(api.analyzeImage).mockResolvedValue({ success: true, description: "A circuit board." });
    render(<ImageUnderstandingPanel />);
    fireEvent.change(screen.getByLabelText("Image file"), { target: { files: [pngFile()] } });
    fireEvent.change(screen.getByLabelText("What should Lumira inspect?"), { target: { value: "Inspect this board" } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze image" }));
    await waitFor(() => expect(api.analyzeImage).toHaveBeenCalledWith(expect.any(String), "Inspect this board"));
    expect(await screen.findByText("A circuit board.")).toBeTruthy();
  });

  it("rejects unsupported file types before calling the API", async () => {
    render(<ImageUnderstandingPanel />);
    const file = new File(["plain text"], "notes.txt", { type: "text/plain" });
    fireEvent.change(screen.getByLabelText("Image file"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze image" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Only PNG, JPEG, and WebP");
    expect(api.analyzeImage).not.toHaveBeenCalled();
  });

  it("retries a failed report save without duplicating the already-saved image", async () => {
    vi.mocked(api.analyzeImage).mockResolvedValue({ success: true, description: "A circuit board." });
    vi.mocked(api.createBinaryArtifact).mockResolvedValue({
      success: true,
      artifact: { artifact_id: "image-1" },
    });
    vi.mocked(api.createArtifact)
      .mockRejectedValueOnce(new Error("Report storage temporarily failed"))
      .mockResolvedValueOnce({ success: true, artifact: { artifact_id: "report-1" } });

    render(<ImageUnderstandingPanel />);
    fireEvent.change(screen.getByLabelText("Image file"), { target: { files: [pngFile()] } });
    fireEvent.change(screen.getByLabelText("What should Lumira inspect?"), { target: { value: "Inspect this board" } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze image" }));
    expect(await screen.findByText("A circuit board.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Save image + analysis to Artifact Manager" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("Retry to save the report without duplicating the image");

    fireEvent.click(screen.getByRole("button", { name: "Save image + analysis to Artifact Manager" }));
    expect(await screen.findByRole("status")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("image-1");
    expect(screen.getByRole("status").textContent).toContain("report-1");
    expect(api.createBinaryArtifact).toHaveBeenCalledTimes(1);
    expect(api.createArtifact).toHaveBeenCalledTimes(2);
    expect(api.createBinaryArtifact).toHaveBeenCalledWith(expect.objectContaining({ extension: "png", type: "images" }));
  });

});
