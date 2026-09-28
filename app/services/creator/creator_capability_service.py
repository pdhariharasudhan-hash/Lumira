"""
Deterministic Creator capability service.
"""

from typing import Any, Dict


class CreatorCapabilityService:

    def content_planning(self, request):
        return self._result("content_planning", request, "content planning",
            ["define audience", "define objective", "define topic",
             "define format", "define content structure", "define publishing requirements"])

    def presentations(self, request):
        return self._result("presentations", request, "presentation creation",
            ["define presentation objective", "define audience", "outline sections",
             "define slide content", "define visual requirements", "verify structure"])

    def posters(self, request):
        return self._result("posters", request, "poster creation",
            ["define poster objective", "define audience", "define headline",
             "define supporting information", "define visual hierarchy", "verify final layout"])

    def thumbnails(self, request):
        return self._result("thumbnails", request, "thumbnail creation",
            ["define content subject", "define visual focus", "define headline",
             "define composition", "define branding requirements", "verify readability"])

    def scripts(self, request):
        return self._result("scripts", request, "script creation",
            ["define objective", "define audience", "outline structure",
             "write sections", "review flow", "verify requirements"])

    def storyboards(self, request):
        return self._result("storyboards", request, "storyboard creation",
            ["define sequence", "define scenes", "define visual actions",
             "define transitions", "define audio requirements", "verify sequence"])

    def ui_concepts(self, request):
        return self._result("ui_concepts", request, "UI concept creation",
            ["define user objective", "identify interface requirements",
             "define information hierarchy", "define interaction flow",
             "define visual structure", "verify usability requirements"])

    def marketing_assets(self, request):
        return self._result("marketing_assets", request, "marketing asset creation",
            ["define campaign objective", "define audience", "define message",
             "define asset format", "define branding", "verify asset requirements"])

    @staticmethod
    def _result(capability, request, objective, steps):
        normalized = request.strip() if isinstance(request, str) else ""
        if not normalized or len(normalized) > 10_000:
            return {"success": False, "status": "rejected", "code": "invalid_request", "capability": capability}
        output = {
            "success": True,
            "capability": capability,
            "request": normalized,
            "objective": objective,
            "steps": list(steps),
            "status": "accept",
        }
        try:
            import json
            from app.services.artifacts.artifact_manager_service import ArtifactManagerService

            output["artifact"] = ArtifactManagerService().create_artifact(
                "exports",
                json.dumps({
                    "type": "creator_plan",
                    "capability": capability,
                    "request": normalized,
                    "objective": objective,
                    "steps": list(steps),
                    "status": "plan_only_external_content_generation_unavailable",
                }, ensure_ascii=False),
                capability,
                "json",
            )
        except Exception:
            return {
                "success": False,
                "status": "failed",
                "code": "artifact_storage_failed",
                "capability": capability,
                "message": "Creator plan could not be stored as an artifact.",
            }
        return output
