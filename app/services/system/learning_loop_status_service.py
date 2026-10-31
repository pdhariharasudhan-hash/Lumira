class LearningLoopStatusService:
    def __init__(self, pattern_service, recommendation_service):
        self.pattern_service = pattern_service
        self.recommendation_service = recommendation_service

    def status(self, project_id=None):
        pattern = self.pattern_service.summary(project_id)
        recommendation = self.recommendation_service.recommend(project_id)
        return {
            "success": True,
            "learning_active": pattern.get("samples", 0) > 0,
            "samples": pattern.get("samples", 0),
            "pattern": pattern.get("pattern"),
            "recommendation": recommendation.get("recommendation"),
        }
