from app.services.system.outcome_pattern_service import OutcomePatternService
from app.services.system.learning_recommendation_service import LearningRecommendationService

class FakeMemory:
    def _read_cognitive_memory(self):
        return {"experiences": [
            {"outcome": "failure", "project_id": "p"},
            {"outcome": "failure", "project_id": "p"},
            {"outcome": "success", "project_id": "p"},
        ]}

def test_failure_pattern_generates_review_recommendation():
    pattern = OutcomePatternService(FakeMemory())
    result = pattern.summary("p")
    assert result["pattern"] == "failure_trend"
    recommendation = LearningRecommendationService(pattern).recommend("p")
    assert recommendation["recommendation"] == "review_strategy_and_recent_failures"
