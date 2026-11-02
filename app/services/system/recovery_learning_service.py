class RecoveryLearningService:
    """Summarize explicitly supplied recovery records for deterministic guidance."""

    def __init__(self, outcome_service):
        self.outcome_service = outcome_service

    def summary(self, records):
        if not isinstance(records, list):
            raise ValueError("records must be a list")
        outcomes = [self.outcome_service.classify(record)["outcome"] for record in records]
        counts = {name: outcomes.count(name) for name in sorted(set(outcomes))}
        return {"success": True, "total": len(records), "outcomes": counts}
