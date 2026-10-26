import { useState, type FormEvent } from "react";
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
