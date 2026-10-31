class BlockerInsightsService:
    def __init__(self, blocker_service):
        self.blocker_service = blocker_service

    def summary(self, project_id=None):
        result = self.blocker_service.list(project_id=project_id, limit=200)
        items = result.get("blockers", [])
        kinds = {}
        for item in items:
            kind = item.get("kind", "unknown") if isinstance(item, dict) else "unknown"
            kinds[kind] = kinds.get(kind, 0) + 1
        return {"success": True, "total": len(items), "by_kind": kinds}
