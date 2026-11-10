"""
Deterministic Creator capability service.
"""

from typing import Any, Dict


class CreatorCapabilityService:

    _OUTPUT_KINDS = {
        "content_planning": "document",
        "presentations": "presentation",
        "posters": "poster",
        "thumbnails": "thumbnail",
        "scripts": "script",
        "storyboards": "storyboard",
        "ui_concepts": "ui_mockup",
        "marketing_assets": "marketing_brief",
    }

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

    @classmethod
    def _result(cls, capability, request, objective, steps):
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
        try:
            from app.services.creator.creator_os_service import CreatorOSService

            creator_kind = cls._OUTPUT_KINDS[capability]
            creator_result = CreatorOSService().create(
                kind=creator_kind,
                title=f"Lumira {objective}",
                brief=normalized,
                audience="Lumira user",
            )
            if creator_result.get("success") is True:
                output["creator_artifact"] = creator_result["artifact"]
                output["creator_output"] = {
                    "kind": creator_result["kind"],
                    "format": creator_result["format"],
                    "status": creator_result["status"],
                }
            else:
                output["creator_output"] = {
                    "status": "unavailable",
                    "message": "Creator artifact integration did not produce an artifact.",
                }
        except (KeyError, OSError, ValueError):
            output["creator_output"] = {
                "status": "unavailable",
                "message": "Creator artifact integration is unavailable; the planning artifact was preserved.",
            }
        return output
