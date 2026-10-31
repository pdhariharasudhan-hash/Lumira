class RecoveryLearningService:
    """Summarize recovery outcomes for future deterministic guidance."""

    def __init__(self, memory_service, outcome_service):
        self.memory_service = memory_service
        self.outcome_service = outcome_service

    def summary(self, project_id=None):
        records = self.memory_service.get_recoveries(project_id)
        outcomes = [self.outcome_service.classify(record)["outcome"] for record in records]
        counts = {name: outcomes.count(name) for name in sorted(set(outcomes))}
        return {"success": True, "project_id": project_id, "total": len(records), "outcomes": counts}
