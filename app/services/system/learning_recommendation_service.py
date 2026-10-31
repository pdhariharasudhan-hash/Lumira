class LearningRecommendationService:
    def __init__(self, pattern_service):
        self.pattern_service = pattern_service

    def recommend(self, project_id=None):
        pattern = self.pattern_service.summary(project_id)
        value = pattern.get("pattern")
        recommendation = {
            "failure_trend": "review_strategy_and_recent_failures",
            "success_trend": "continue_current_execution_strategy",
            "insufficient_data": "collect_more_execution_outcomes",
        }.get(value, "collect_more_execution_outcomes")
        return {"success": True, "recommendation": recommendation, "pattern": pattern}
