import { useEffect, useState, type FormEvent } from "react";
import { api } from "../../api/client";

const MAX_IMAGE_BYTES = 10_000_000;

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("The selected image could not be read."));
    reader.onload = () => {
      if (typeof reader.result !== "string") {
        reject(new Error("The selected image could not be encoded."));
        return;
      }
      const comma = reader.result.indexOf(",");
      if (comma < 0) {
        reject(new Error("The selected image could not be encoded."));
        return;
      }
      resolve(reader.result.slice(comma + 1));
    };
    reader.readAsDataURL(file);
  });
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

export function ImageUnderstandingPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState("Describe this image and extract any readable text.");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [savingReport, setSavingReport] = useState(false);
  const [savedImageArtifactId, setSavedImageArtifactId] = useState("");
  const [savedReportArtifactId, setSavedReportArtifactId] = useState("");
  const [savedReport, setSavedReport] = useState("");
  const [visionProviderState, setVisionProviderState] = useState<Record<string, unknown> | null>(null);
  const [providerStatusLoading, setProviderStatusLoading] = useState(true);
  const [providerStatusError, setProviderStatusError] = useState("");
  const [providerStatusRefresh, setProviderStatusRefresh] = useState(0);
  const [storedArtifactId, setStoredArtifactId] = useState("");
  const [storedAnalysis, setStoredAnalysis] = useState<Record<string, unknown> | null>(null);
  const [storedAnalysisLoading, setStoredAnalysisLoading] = useState(false);

  useEffect(() => {
    let current = true;
    setProviderStatusLoading(true);
    setProviderStatusError("");
    api.providerStatus()
      .then((result) => {
        if (current) setVisionProviderState(asRecord(asRecord(result.providers).image_understanding));
      })
      .catch((cause: unknown) => {
        if (!current) return;
        setVisionProviderState(null);
        setProviderStatusError(cause instanceof Error ? cause.message : "Provider status could not be loaded.");
      })
      .finally(() => {
        if (current) setProviderStatusLoading(false);
      });
    return () => { current = false; };
  }, [providerStatusRefresh]);

  const providerRegistered = visionProviderState?.registered === true;
  const providerConfigured = visionProviderState?.configured === true;
  const providerImplementation = typeof visionProviderState?.implementation === "string"
    ? visionProviderState.implementation
    : "Configured provider";
  const providerExecutionMode = visionProviderState?.execution_mode === "local" ? "local" : "remote/external";

  async function saveAnalysis() {
    if (!description.trim() || !file || savingReport) return;
    setSavingReport(true);
    setError("");
    let imageWasSaved = Boolean(savedImageArtifactId);
    try {
      let imageArtifactId = savedImageArtifactId;
      if (!imageArtifactId) {
        const imageExtension = file.type === "image/jpeg" ? "jpg" : file.type === "image/webp" ? "webp" : "png";
        const imageBase64 = await fileToBase64(file);
        const imageResult = await api.createBinaryArtifact({
          type: "images",
          content_base64: imageBase64,
          source: `image_analysis_source:${file.name}`,
          extension: imageExtension,
        });
        const imageRecord = typeof imageResult.artifact === "object" && imageResult.artifact !== null
          ? imageResult.artifact as Record<string, unknown>
          : {};
        imageArtifactId = typeof imageRecord.artifact_id === "string"
          ? imageRecord.artifact_id
          : typeof imageResult.artifact_id === "string" ? imageResult.artifact_id : "";
        if (imageResult.success !== true) {
          throw new Error("The original image could not be saved to Artifact Manager.");
        }
        imageWasSaved = true;
        setSavedImageArtifactId(imageArtifactId || "saved");
      }

      if (!savedReportArtifactId) {
        const title = `Image analysis — ${file.name}`;
        const imageReference = imageArtifactId && imageArtifactId !== "saved"
          ? imageArtifactId
          : "Saved to Artifact Manager";
        const content = `# ${title}\n\n**Original image artifact:** ${imageReference}\n\n**Image:** ${file.name}\n\n**Inspection request:**\n${prompt.trim()}\n\n**Lumira analysis:**\n${description.trim()}\n`;
        const result = await api.createArtifact({
          type: "reports",
          content,
          source: `image_analysis:${file.name}`,
          extension: "md",
        });
        const reportRecord = typeof result.artifact === "object" && result.artifact !== null
          ? result.artifact as Record<string, unknown>
          : {};
        const reportArtifactId = typeof reportRecord.artifact_id === "string"
          ? reportRecord.artifact_id
          : typeof result.artifact_id === "string" ? result.artifact_id : "";
        if (result.success !== true) {
          throw new Error("The analysis report could not be saved to Artifact Manager.");
        }
        setSavedReportArtifactId(reportArtifactId || "saved");
        setSavedReport(
          imageArtifactId && imageArtifactId !== "saved" && reportArtifactId
            ? `Saved original image (${imageArtifactId}) and analysis report (${reportArtifactId}) to Artifact Manager.`
            : "Saved the original image and analysis report to Artifact Manager.",
        );
      } else {
        setSavedReport("The image and analysis report are saved to Artifact Manager.");
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "The analysis could not be saved.";
      setError(imageWasSaved
        ? `The original image is saved. ${message} Retry to save the report without duplicating the image.`
        : message);
    } finally {
      setSavingReport(false);
    }
  }
  async function analyzeStoredArtifact() {
    const artifactId = storedArtifactId.trim();
    if (!artifactId || storedAnalysisLoading) return;
    setStoredAnalysisLoading(true);
    setError("");
    setStoredAnalysis(null);
    try {
      const result = await api.analyzeImageArtifact(artifactId, prompt.trim(), true);
      setStoredAnalysis(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Stored image analysis failed.");
    } finally {
      setStoredAnalysisLoading(false);
    }
  }

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setDescription("");
    setSavedReport("");
    setSavedReportArtifactId("");
    if (!file) {
      setError("Choose a PNG, JPEG, or WebP image first.");
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setError("The image must be 10 MB or smaller.");
      return;
    }
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      setError("Only PNG, JPEG, and WebP images are supported.");
      return;
    }
    if (!prompt.trim()) {
      setError("Enter what Lumira should inspect in the image.");
      return;
    }
    setLoading(true);
    try {
      const image_base64 = await fileToBase64(file);
      const result = await api.analyzeImage(image_base64, prompt.trim());
      setDescription(typeof result.description === "string" ? result.description : "No description was returned.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Image analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="image-analysis-page">
      <header className="workspace-page-heading">
        <div>
          <span className="eyebrow">MULTIMODAL</span>
          <h2>Image Analysis</h2>
          <p>Ask Lumira to describe an image, inspect a circuit, or extract readable text. A configured vision provider is required.</p>
        </div>
      </header>
      <div className="image-analysis-message" aria-live="polite">
        <div className="entity-actions">
          <strong>Vision provider</strong>
          <span className="status-pill">
            {providerStatusLoading ? "Checking…" : providerStatusError ? "Unknown" : providerRegistered ? "Registered" : providerConfigured ? "Configured, not registered" : "Not configured"}
          </span>
          <button className="secondary-action" type="button" disabled={providerStatusLoading} onClick={() => setProviderStatusRefresh((value) => value + 1)}>
            {providerStatusLoading ? "Refreshing…" : "Refresh status"}
          </button>
        </div>
        {providerStatusError
          ? <p role="alert">Could not load provider status: {providerStatusError}</p>
          : providerRegistered
            ? <p>{providerImplementation} · {providerExecutionMode}. Registration confirms configuration only; it does not prove the model is installed or reachable. An analysis request verifies actual availability.</p>
            : providerConfigured
              ? <p>A vision provider is enabled in configuration but was not registered. Check the relevant API key or local provider setup, then refresh.</p>
              : <p>No vision provider is registered. Configure either the remote vision provider with its API key or enable local Ollama vision.</p>}
      </div>
      <section className="image-analysis-message">
        <h3>Analyze an image already in Artifact Manager</h3>
        <p>Enter an existing image artifact ID. Lumira will analyze the stored file and can save a linked report without uploading the image again.</p>
        <label>
          Image artifact ID
          <input
            value={storedArtifactId}
            onChange={(event) => setStoredArtifactId(event.target.value)}
            placeholder="Paste an image artifact ID"
            maxLength={128}
            disabled={storedAnalysisLoading}
          />
        </label>
        <button className="secondary-action" type="button" disabled={storedAnalysisLoading || !storedArtifactId.trim() || !prompt.trim()} onClick={() => void analyzeStoredArtifact()}>
          {storedAnalysisLoading ? "Analyzing stored image…" : "Analyze stored image"}
        </button>
        {storedAnalysis && (
          <div className="image-analysis-result" aria-live="polite">
            <h3>Stored image analysis</h3>
            <p>{typeof storedAnalysis.description === "string" ? storedAnalysis.description : "No description was returned."}</p>
            <p>Source artifact: {String(storedAnalysis.source_artifact_id ?? storedArtifactId)}</p>
            {typeof storedAnalysis.artifact === "object" && storedAnalysis.artifact !== null && (
              <p>Report artifact: {String((storedAnalysis.artifact as Record<string, unknown>).artifact_id ?? "saved")}</p>
            )}
            {storedAnalysis.artifact_saved === true && <p role="status">Analysis report saved and linked to the source image.</p>}
          </div>
        )}
      </section>
      <form className="image-analysis-form" onSubmit={(event) => void analyze(event)}>
        <label>
          Image file
          <input type="file" accept="image/png,image/jpeg,image/webp" disabled={loading || savingReport} onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
            setDescription("");
            setError("");
            setSavedImageArtifactId("");
            setSavedReportArtifactId("");
            setSavedReport("");
          }} />
        </label>
        {file && <p className="image-analysis-file">{file.name} · {(file.size / (1024 * 1024)).toFixed(2)} MB</p>}
        <label>
          What should Lumira inspect?
          <textarea rows={4} maxLength={4000} value={prompt} onChange={(event) => setPrompt(event.target.value)} />
        </label>
        <button className="primary-action" type="submit" disabled={loading || !file}>
          {loading ? "Analyzing…" : "Analyze image"}
        </button>
      </form>
      {error && <div className="image-analysis-message is-error" role="alert">{error}</div>}
      {description && <section className="image-analysis-result" aria-live="polite"><h3>Analysis</h3><p>{description}</p><button className="primary-action" type="button" disabled={savingReport || Boolean(savedReport)} onClick={() => void saveAnalysis()}>{savingReport ? "Saving image and report…" : savedReport ? "Saved to Artifact Manager" : "Save image + analysis to Artifact Manager"}</button>{savedReport && <p role="status">{savedReport}</p>}</section>}
    </section>
  );
}
