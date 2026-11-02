class ExecutionReadinessService:
    def __init__(self, action_service, blocker_service):
        self.action_service = action_service
        self.blocker_service = blocker_service

    def status(self, project_id=None):
        actions = self.action_service.ready(project_id=project_id)
        blockers = self.blocker_service.list(project_id=project_id, limit=200)
        ready_count = actions.get("count", len(actions.get("actions", [])))
        blocker_count = blockers.get("count", len(blockers.get("blockers", [])))
        return {
            "success": True,
            "ready_action_count": ready_count,
            "blocker_count": blocker_count,
            "state": "blocked" if blocker_count else ("ready" if ready_count else "idle"),
        }
