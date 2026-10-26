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


def test_feature_list_phrases_route_to_list_features():
    parser = CommandParserService()
    for command in ("list features", "list all features", "show features", "show me features"):
        parsed = parser.parse(command)
        assert parsed["success"] is True
        assert parsed["capability"] == "list_features"
