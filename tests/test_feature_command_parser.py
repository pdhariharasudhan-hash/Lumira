from app.services.command_parser_service import CommandParserService


def test_feature_status_commands_route_to_feature_status():
    parser = CommandParserService()
    cases = {
        "feature status image generation": "image generation",
        "status of feature voice capture": "voice capture",
        "check feature artifact manager": "artifact manager",
        "is feature unified search enabled": "unified search",
    }

    for command, feature in cases.items():
        parsed = parser.parse(command)
        assert parsed["success"] is True
        assert parsed["capability"] == "feature_status"
        assert parsed["payload"]["feature"] == feature


def test_feature_status_command_rejects_missing_name():
    parsed = CommandParserService().parse("feature status ")
    assert parsed["success"] is False


def test_complete_project_commands_route_to_existing_pipeline():
    parser = CommandParserService()
    for command in (
        "build the complete project for a notes API",
        "build full project for my personal assistant",
        "build all features for a task manager",
    ):
        parsed = parser.parse(command)
        assert parsed["success"] is True
        assert parsed["capability"] == "project_pipeline"
        assert parsed["payload"]["request"] == command


def test_assistant_commands_route_to_existing_capabilities():
    parser = CommandParserService()
    cases = {
        "schedule my study session": "scheduling",
        "plan my day": "daily_planning",
        "notify me when work is done": "notifications",
        "organize my work": "personal_organization",
        "draft an email to my teacher": "email",
        "enable voice assistant": "voice",
    }

    for command, capability in cases.items():
        parsed = parser.parse(command)
        assert parsed["success"] is True
        assert parsed["capability"] == capability
        assert parsed["payload"]["request"] == command


def test_feature_list_phrases_route_to_list_features():
    parser = CommandParserService()
    for command in ("list features", "list all features", "show features", "show me features"):
        parsed = parser.parse(command)
        assert parsed["success"] is True
        assert parsed["capability"] == "list_features"

from app.services.projects.project_classifier import ProjectClassifier


def test_image_generation_accepts_common_natural_language_variants():
    parser = CommandParserService()
    for command in (
        "GENERATE A IMAGE OF ROCKET",
        "create an image of a rocket",
        "draw a picture of a rocket",
    ):
        parsed = parser.parse(command)
        assert parsed["success"] is True
        assert parsed["capability"] == "generate_image"
        assert parsed["payload"]["prompt"] == command


def test_vague_app_request_asks_for_requirements_instead_of_running_builder():
    parsed = CommandParserService().parse("Build an app")
    assert parsed == {
        "success": True,
        "capability": "clarify_project",
        "payload": {},
    }


def test_specific_app_request_gets_a_crud_project_plan():
    classifier = ProjectClassifier()
    result = classifier.classify("build an app for tracking homework")
    assert result["primary_entity"] == "homework"
    assert set(result["actions"]) >= {"storage", "create", "read", "update", "delete"}
