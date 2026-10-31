class AdaptiveExecutionService:
    def __init__(self, decision_service, learning_service):
        self.decision_service = decision_service
        self.learning_service = learning_service

    def guidance(self, project_id=None):
        decision = self.decision_service.snapshot(project_id)
        learning = self.learning_service.recommend(project_id)
        recommendation = learning["recommendation"] if learning["pattern"]["pattern"] == "failure_trend" else decision["recommendation"]
        return {"success": True, "recommendation": recommendation, "decision": decision, "learning": learning}
