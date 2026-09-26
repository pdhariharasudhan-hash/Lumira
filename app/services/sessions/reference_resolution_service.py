import re


REFERENCE_PATTERN = re.compile(
    r"\b(it|this|that|the project|the api|that api|this api)\b",
    re.IGNORECASE,
)


class ReferenceResolutionService:
    """Resolve project references only from explicit active session context."""

    def resolve(self, text: str, session: dict) -> dict:
        if not REFERENCE_PATTERN.search(text):
            return {"status": "not_applicable", "project_id": None}

        active_project = session.get("active_project")
        if active_project:
            return {
                "status": "resolved",
                "project_id": active_project,
                "reference": REFERENCE_PATTERN.search(text).group(0),
            }

        references = session.get("conversation", {}).get("recent_references", [])
        candidates = sorted({value for value in references if isinstance(value, str) and value})
        if len(candidates) == 1:
            return {
                "status": "resolved",
                "project_id": candidates[0],
                "reference": REFERENCE_PATTERN.search(text).group(0),
            }
        if len(candidates) > 1:
            return {"status": "ambiguous", "candidates": candidates}
        return {"status": "unresolved", "candidates": []}
