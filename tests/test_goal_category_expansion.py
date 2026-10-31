from app.services.goals.goal_service import GoalService


def test_engineering_goal_category():
    assert GoalService()._detect_category("Build an ESP32 robot") == "hardware"


def test_education_goal_category():
    assert GoalService()._detect_category("Study physics for an exam") == "education"


def test_business_goal_category():
    assert GoalService()._detect_category("Improve startup revenue and sales") == "business"
