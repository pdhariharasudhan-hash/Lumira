"""Creator OS: deterministic, editable text/vector deliverables stored as artifacts."""
from __future__ import annotations
import html
import json
import re
from app.services.artifacts.artifact_manager_service import ArtifactManagerService


class CreatorOSService:
    KINDS = {"poster", "logo", "thumbnail", "infographic", "ui_mockup", "blueprint", "presentation", "storyboard", "script", "video_script", "social_post", "document", "marketing_brief"}

    def __init__(self, artifacts=None):
        self.artifacts = artifacts or ArtifactManagerService()

    @staticmethod
    def _text(value, name, limit=5000):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"{name} must contain 1-{limit} characters")
        return value.strip()

    def create(self, kind: str, title: str, brief: str, audience: str = "General", slides: list[str] | None = None) -> dict:
        if kind not in self.KINDS:
            raise ValueError("unsupported creator output kind")
        title = self._text(title, "title", 160)
        brief = self._text(brief, "brief", 12000)
        audience = self._text(audience, "audience", 160)
        if slides is not None and (not isinstance(slides, list) or len(slides) > 30 or any(not isinstance(x, str) or not x.strip() or len(x) > 2000 for x in slides)):
            raise ValueError("slides must contain at most 30 non-empty text entries of at most 2000 characters")
        safe_title, safe_brief, safe_audience = map(html.escape, (title, brief, audience))
        if kind in {"poster", "logo", "thumbnail", "infographic", "ui_mockup", "blueprint"}:
            subtitle = html.escape(brief[:220])
            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1500" viewBox="0 0 1200 1500">
<rect width="1200" height="1500" fill="#101827"/><rect x="70" y="70" width="1060" height="1360" rx="36" fill="none" stroke="#7dd3fc" stroke-width="4"/>
<text x="110" y="300" fill="#f8fafc" font-family="Arial,sans-serif" font-size="76" font-weight="700">{safe_title[:70]}</text>
<foreignObject x="110" y="390" width="980" height="520"><div xmlns="http://www.w3.org/1999/xhtml" style="color:#cbd5e1;font:34px Arial;line-height:1.4">{subtitle}</div></foreignObject>
<text x="110" y="1320" fill="#7dd3fc" font-family="Arial,sans-serif" font-size="24">CREATOR OS • EDITABLE VECTOR CONCEPT</text></svg>'''
            artifact = self.artifacts.create_artifact("diagrams", svg, f"creator_{kind}", "svg")
            format_name = "svg"
        elif kind == "presentation":
            sections = slides or [part.strip() for part in re.split(r"\n\s*\n", brief) if part.strip()]
            sections = sections[:30] or [brief]
            pages = "".join(f'<section class="slide"><h2>{html.escape(str(i+1)+". "+title)}</h2><p>{html.escape(text)}</p></section>' for i, text in enumerate(sections))
            document = f'<!doctype html><html><head><meta charset="utf-8"><title>{safe_title}</title><style>body{{font-family:Arial;background:#0f172a;color:#e2e8f0;margin:0}}.slide{{min-height:90vh;padding:6vw;box-sizing:border-box;border-bottom:1px solid #334155}}h1{{color:#7dd3fc}}h2{{font-size:2.4rem}}p{{font-size:1.5rem;line-height:1.6;white-space:pre-wrap}}</style></head><body><section class="slide"><h1>{safe_title}</h1><p>Audience: {safe_audience}</p><p>{safe_brief}</p></section>{pages}</body></html>'
            artifact = self.artifacts.create_artifact("exports", document, "creator_presentation", "html")
            format_name = "html"
        elif kind == "storyboard":
            scenes = slides or [part.strip() for part in re.split(r"\n\s*\n", brief) if part.strip()]
            payload = {"title": title, "audience": audience, "brief": brief, "scenes": [{"scene": i+1, "description": scene, "visual_direction": "", "camera": "", "audio": "", "duration_seconds": None} for i, scene in enumerate(scenes[:50])], "status": "storyboard_only_video_not_rendered"}
            artifact = self.artifacts.create_artifact("exports", json.dumps(payload, ensure_ascii=False, indent=2), "creator_storyboard", "json")
            format_name = "json"
        else:
            heading = title
            body = f"# {heading}\n\n**Audience:** {audience}\n\n## Brief\n\n{brief}\n\n## Production notes\n\n- Confirm factual claims and required approvals.\n- Review accessibility, readability and brand consistency.\n- Export/rendering beyond this text artifact requires a configured media provider.\n"
            extension = "md"
            artifact = self.artifacts.create_artifact("exports", body, f"creator_{kind}", extension)
            format_name = extension
        return {"success": True, "kind": kind, "title": title, "format": format_name, "artifact": artifact,
                "status": "artifact_created", "rendering_note": "This creates an editable text/vector artifact. It does not claim to render raster images or video."}

    def synthesize_audio(self, text: str, language: str = "en") -> dict:
        from app.services.providers.provider_registry import ProviderRegistry
        from app.services.providers.provider_access_policy_service import ProviderAccessPolicyService, ProviderAccessDenied
        if not isinstance(text, str) or not text.strip() or len(text) > 20000:
            raise ValueError("audio text must contain 1-20000 characters")
        if language not in {"en", "ta", "ta-en"}:
            raise ValueError("language must be en, ta, or ta-en")
        provider = ProviderRegistry.get("speech_synthesis")
        if provider is None:
            return {"success": False, "code": "speech_provider_unavailable", "message": "Configure and enable a speech synthesis provider first."}
        try:
            ProviderAccessPolicyService().authorize(provider, "creator audio generation")
            result = provider.synthesize(text.strip(), language)
        except ProviderAccessDenied as exc:
            return {"success": False, "code": exc.code, "message": exc.user_message}
        except RuntimeError:
            return {"success": False, "code": "speech_provider_error", "message": "Speech generation failed or was deferred by resource policy."}
        except Exception:
            return {"success": False, "code": "speech_provider_error", "message": "Speech provider failed; no audio artifact was saved."}
        if not isinstance(result, dict) or result.get("success") is not True or not isinstance(result.get("content"), bytes):
            return {"success": False, "code": "speech_provider_invalid_response", "message": "Speech provider returned no validated audio."}
        artifact = self.artifacts.create_binary_artifact("audio", result["content"], "creator_os_speech_synthesis", result.get("extension", "mp3"))
        return {"success": True, "kind": "audio", "format": result.get("extension", "mp3"), "artifact": artifact, "status": "artifact_created"}


    def generate_video(self, prompt: str, duration_seconds: int = 5, aspect_ratio: str = "16:9") -> dict:
        from app.services.providers.provider_registry import ProviderRegistry
        from app.services.providers.provider_access_policy_service import ProviderAccessPolicyService, ProviderAccessDenied
        prompt = self._text(prompt, "video prompt", 12000)
        if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, int) or not 1 <= duration_seconds <= 60:
            raise ValueError("duration_seconds must be between 1 and 60")
        if aspect_ratio not in {"16:9", "9:16", "1:1"}:
            raise ValueError("aspect_ratio must be 16:9, 9:16 or 1:1")
        provider = ProviderRegistry.get("video_generation")
        if provider is None:
            return {"success": False, "code": "video_provider_unavailable",
                    "message": "No video-generation provider is registered. Storyboard artifacts remain available."}
        try:
            ProviderAccessPolicyService().authorize(provider, "creator video generation")
            result = provider.generate_video(prompt=prompt, duration_seconds=duration_seconds, aspect_ratio=aspect_ratio)
        except ProviderAccessDenied as exc:
            return {"success": False, "code": exc.code, "message": exc.user_message}
        except Exception:
            return {"success": False, "code": "video_provider_error", "message": "Video provider failed; no video artifact was saved."}
        if not isinstance(result, dict) or result.get("success") is not True or not isinstance(result.get("content"), bytes):
            return {"success": False, "code": "video_provider_invalid_response", "message": "Video provider returned no validated video bytes."}
        extension = str(result.get("extension", "mp4")).lower().lstrip(".")
        if extension not in {"mp4", "webm"}:
            return {"success": False, "code": "video_provider_invalid_format", "message": "Only MP4 and WebM video artifacts are accepted."}
        artifact = self.artifacts.create_binary_artifact("video", result["content"], "creator_os_video_generation", extension)
        return {"success": True, "kind": "video", "format": extension, "artifact": artifact, "status": "artifact_created"}
