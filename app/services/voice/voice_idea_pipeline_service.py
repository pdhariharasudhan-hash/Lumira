"""End-to-end voice idea processing using existing Lumira services."""

from app.services.language.language_detection_service import LanguageDetectionService
from app.services.memory.memory_service import MemoryService
from app.services.response.summary_service import SummaryService
from app.services.voice.transcript_service import TranscriptService


class VoiceIdeaPipelineService:
    """Connect audio -> transcript -> language -> summary -> memory."""

    def __init__(
        self,
        transcript_service=None,
        summary_service=None,
        memory_service=None,
        language_service=None,
    ):
        self.transcripts = transcript_service or TranscriptService()
        self.summaries = summary_service or SummaryService()
        self.memory = memory_service or MemoryService()
        self.languages = language_service or LanguageDetectionService()

    def inspect_transcript(self, transcript_artifact_id: str) -> dict:
        if not isinstance(transcript_artifact_id, str) or not transcript_artifact_id.strip():
            return {"success": False, "code": "invalid_transcript_artifact"}
        summary = self.summaries.generate_summary(transcript_artifact_id.strip())
        return {
            "success": bool(summary.get("success")),
            "stage": "complete" if summary.get("success") else "summary",
            "transcript_artifact": transcript_artifact_id.strip(),
            "summary": summary,
            "recoverable": not bool(summary.get("success")),
        }

    def retry(self, audio_artifact_id: str, project_id: str | None = None, goal_id: str | None = None) -> dict:
        """Retry the complete pipeline while preserving explicit context."""
        return self.process(audio_artifact_id, project_id=project_id, goal_id=goal_id)

    def retry_summary(self, transcript_artifact_id: str) -> dict:
        """Retry summarization and attach its artifact to any existing voice memory."""
        if not isinstance(transcript_artifact_id, str) or not transcript_artifact_id.strip():
            return {"success": False, "code": "invalid_transcript_artifact"}
        transcript_id = transcript_artifact_id.strip()
        result = self.inspect_transcript(transcript_id)
        if result.get("success") is not True:
            return result

        summary_record = result.get("summary", {}).get("summary_artifact")
        summary_id = summary_record.get("artifact_id") if isinstance(summary_record, dict) else None
        if not isinstance(summary_id, str) or not summary_id:
            return {
                **result,
                "success": False,
                "stage": "summary",
                "code": "missing_summary_artifact",
                "recoverable": True,
            }

        get_all = getattr(self.memory, "get_all", None)
        attach = getattr(self.memory, "attach_artifacts_to_experience", None)
        if not callable(get_all) or not callable(attach):
            return result
        try:
            data = get_all()
            experiences = data.get("experiences", []) if isinstance(data, dict) else []
            existing = next((
                item for item in experiences
                if isinstance(item, dict)
                and isinstance(item.get("artifact_ids"), list)
                and transcript_id in item["artifact_ids"]
            ), None)
            if existing is None:
                return result
            updated = attach(transcript_id, [summary_id])
        except Exception:
            return {
                **result,
                "success": False,
                "stage": "memory",
                "code": "memory_artifact_link_failed",
                "recoverable": True,
                "preserved_artifacts": [transcript_id, summary_id],
                "message": "The summary was saved, but its link to the existing voice memory could not be confirmed. Retry the link operation; the transcript and summary artifacts are preserved.",
            }
        result["memory_reference"] = updated.get("experience_id") if isinstance(updated, dict) else existing.get("experience_id")
        result["memory_status"] = {"success": True, "state": "updated"}
        result["preserved_artifacts"] = list(updated.get("artifact_ids", [])) if isinstance(updated, dict) else [transcript_id, summary_id]
        return result

    def inspect(self, audio_artifact_id: str) -> dict:
        if not isinstance(audio_artifact_id, str) or not audio_artifact_id.strip():
            return {"success": False, "code": "invalid_audio_artifact"}
        transcript = self.transcripts.generate_transcript(audio_artifact_id.strip())
        return {"success": bool(transcript.get("success")), "stage": "transcript", "audio_artifact": audio_artifact_id, "transcript": transcript}

    def _existing_voice_experience(self, audio_artifact_id: str) -> dict | None:
        """Find a previously persisted voice experience to make retries idempotent."""
        get_all = getattr(self.memory, "get_all", None)
        if not callable(get_all):
            # Keep lightweight injected adapters compatible; the production
            # MemoryService always exposes get_all for the idempotency check.
            return None
        data = get_all()
        experiences = data.get("experiences", []) if isinstance(data, dict) else []
        for record in experiences if isinstance(experiences, list) else []:
            artifact_ids = record.get("artifact_ids", []) if isinstance(record, dict) else []
            if isinstance(record, dict) and isinstance(artifact_ids, list) and audio_artifact_id in artifact_ids:
                return record
        return None

    def process(
        self,
        audio_artifact_id: str,
        project_id: str | None = None,
        goal_id: str | None = None,
    ) -> dict:
        if not isinstance(audio_artifact_id, str) or not audio_artifact_id.strip():
            return {
                "success": False,
                "stage": "validate",
                "code": "invalid_audio_artifact",
            }

        audio_id = audio_artifact_id.strip()
        try:
            existing = self._existing_voice_experience(audio_id)
        except Exception:
            return {
                "success": False,
                "stage": "memory_preflight",
                "code": "memory_lookup_failed",
                "audio_artifact": audio_id,
                "recoverable": True,
                "preserved_artifacts": [audio_id],
                "message": "Existing voice memory could not be checked safely. No duplicate transcription or memory write was started; retry when memory storage is available.",
            }
        if existing is not None:
            return {
                "success": True,
                "stage": "complete",
                "audio_artifact": audio_id,
                "memory_reference": existing.get("experience_id"),
                "memory_status": {"success": True, "state": "already_saved"},
                "preserved_artifacts": list(existing.get("artifact_ids", [])),
                "message": "This voice idea is already processed and linked to memory; no duplicate transcript or memory record was created.",
            }

        transcript = self.transcripts.generate_transcript(audio_id)
        if not transcript.get("success"):
            return {
                "success": False,
                "stage": "transcript",
                "audio_artifact": audio_artifact_id,
                "transcript": transcript,
            }

        transcript_record = transcript.get("transcript_artifact", {})
        transcript_id = (
            transcript_record.get("artifact_id")
            if isinstance(transcript_record, dict)
            else None
        )
        if not transcript_id:
            return {
                "success": False,
                "stage": "transcript",
                "code": "missing_transcript_artifact",
            }

        transcript_text = transcript.get("transcript_text", "")
        if not isinstance(transcript_text, str):
            transcript_text = ""
        language = self.languages.detect(transcript_text)
        summary = self.summaries.generate_summary(transcript_id)

        core_context = {}
        try:
            from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService
            core_context = CoreRuntimeBridgeService().execution_context(
                "voice_idea_process",
                project_id=project_id,
                goal_id=goal_id,
            )
        except Exception:
            core_context = {"success": False, "error": "core_context_unavailable"}

        result = {
            "success": bool(summary.get("success")),
            "stage": "complete" if summary.get("success") else "summary",
            "audio_artifact": audio_artifact_id,
            "transcript": transcript,
            "language": language,
            "summary": summary,
            "core_context": core_context,
        }

        artifact_ids = [audio_artifact_id, transcript_id]
        if not summary.get("success"):
            result["recoverable"] = True
            result["preserved_artifacts"] = artifact_ids.copy()
            return result
        summary_record = summary.get("summary_artifact")
        if isinstance(summary_record, dict) and summary_record.get("artifact_id"):
            artifact_ids.append(summary_record["artifact_id"])

        if summary.get("success"):
            try:
                experience = self.memory.record_experience(
                    "workflow",
                    summary=str(summary.get("summary_text", ""))[:4000],
                    outcome=(
                        "Voice idea captured, transcribed, summarized "
                        "and linked to artifacts"
                    ),
                    project_id=project_id,
                    goal_id=goal_id,
                    artifact_ids=artifact_ids,
                    verified=False,
                )
                result["memory_reference"] = experience.get("experience_id")
                result["memory_status"] = {"success": True, "state": "saved"}
            except Exception:
                result["success"] = False
                result["stage"] = "memory"
                result["recoverable"] = True
                result["preserved_artifacts"] = artifact_ids.copy()
                result["memory_status"] = {
                    "success": False,
                    "code": "memory_persistence_failed",
                    "message": "Voice artifacts are preserved, but the memory record could not be saved. Retry from the saved artifacts.",
                }
        return result
