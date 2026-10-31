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

        transcript = self.transcripts.generate_transcript(audio_artifact_id.strip())
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

        result = {
            "success": bool(summary.get("success")),
            "stage": "complete" if summary.get("success") else "summary",
            "audio_artifact": audio_artifact_id,
            "transcript": transcript,
            "language": language,
            "summary": summary,
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
            experience = self.memory.record_experience(
                "voice_idea",
                summary=str(summary.get("summary_text", ""))[:4000],
                outcome=(
                    "Voice idea captured, transcribed, summarized "
                    "and linked to artifacts"
                ),
                project_id=project_id,
                goal_id=goal_id,
                artifact_ids=artifact_ids,
                verified=True,
            )
            result["memory_reference"] = experience.get("experience_id")
        return result
