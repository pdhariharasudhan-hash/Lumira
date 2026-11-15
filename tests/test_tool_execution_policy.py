import pytest

from app.services.brain.tool_execution_policy_service import ToolExecutionPolicyService


def _manifest(schema):
    return {"name": "checked_tool", "capability": "records.read", "parameters": schema}


def test_schema_rejects_unknown_keywords_instead_of_silently_ignoring_them():
    policy = ToolExecutionPolicyService({"records.read": True})
    schema = {"type": "object", "properties": {"code": {"type": "string", "format": "email"}}}
    result = policy.authorize(_manifest(schema), {"code": "not-an-email"})
    assert result.allowed is False
    assert result.code == "unsupported_schema_keyword"


def test_schema_rejects_unbounded_regex_pattern_keyword():
    policy = ToolExecutionPolicyService({"records.read": True})
    schema = {"type": "object", "properties": {"code": {"type": "string", "pattern": ".*"}}}
    result = policy.authorize(_manifest(schema), {"code": "anything"})
    assert result.allowed is False
    assert result.code == "unsupported_schema_keyword"


def test_enum_is_validated_and_enforced():
    policy = ToolExecutionPolicyService({"records.read": True})
    schema = {
        "type": "object",
        "properties": {"mode": {"type": "string", "enum": ["safe", "read-only"]}},
        "required": ["mode"],
        "additionalProperties": False,
    }
    assert policy.authorize(_manifest(schema), {"mode": "safe"}).allowed is True
    assert policy.authorize(_manifest(schema), {"mode": "unsafe"}).code == "arguments_invalid"
    invalid = {"type": "object", "enum": "not-a-list", "properties": {}}
    assert policy.validate_manifest(_manifest(invalid)).code == "invalid_schema_enum"


def test_nested_invalid_schema_with_enum_fails_closed_without_exception():
    policy = ToolExecutionPolicyService()
    schema = {"type": "object", "enum": [{}], "properties": {"value": {"description": "missing type"}}}
    result = policy.validate_manifest(_manifest(schema))
    assert result.allowed is False


def test_array_unique_items_and_object_property_bounds_are_enforced():
    policy = ToolExecutionPolicyService({"records.read": True})
    schema = {
        "type": "object",
        "properties": {
            "tags": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        },
        "required": ["tags"],
        "minProperties": 1,
        "maxProperties": 1,
        "additionalProperties": False,
    }
    assert policy.authorize(_manifest(schema), {"tags": ["a", "b"]}).allowed is True
    assert policy.authorize(_manifest(schema), {"tags": ["a", "a"]}).code == "arguments_invalid"
    assert policy.authorize(_manifest(schema), {"tags": [], "extra": True}).code == "arguments_invalid"


def test_numeric_exclusive_bounds_and_multiple_of_are_enforced():
    policy = ToolExecutionPolicyService({"records.read": True})
    schema = {
        "type": "object",
        "properties": {
            "amount": {
                "type": "number",
                "exclusiveMinimum": 0,
                "exclusiveMaximum": 10,
                "multipleOf": 0.5,
            }
        },
        "required": ["amount"],
        "additionalProperties": False,
    }
    assert policy.authorize(_manifest(schema), {"amount": 2.5}).allowed is True
    for value in (0, 10, 2.3):
        assert policy.authorize(_manifest(schema), {"amount": value}).code == "arguments_invalid"


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "array", "items": {"type": "string"}, "uniqueItems": "yes"},
        {"type": "object", "properties": {}, "required": ["missing"]},
        {"type": "integer", "multipleOf": 0},
        {"type": "object", "properties": {}, "additionalProperties": {"type": "string"}},
    ],
)
def test_malformed_schema_constraints_are_rejected(schema):
    assert ToolExecutionPolicyService().validate_manifest(_manifest(schema)).allowed is False


def test_manifest_rejects_non_boolean_approval_requirement():
    manifest = _manifest({"type": "object", "properties": {}})
    manifest["requires_approval"] = "yes"
    result = ToolExecutionPolicyService().validate_manifest(manifest)
    assert result.allowed is False
    assert result.code == "invalid_approval_flag"


def test_numeric_schema_rejects_conflicting_inclusive_and_exclusive_bounds():
    schema = {
        "type": "object",
        "properties": {
            "value": {
                "type": "number",
                "minimum": 10,
                "exclusiveMinimum": 20,
                "maximum": 15,
            }
        },
    }
    result = ToolExecutionPolicyService().validate_manifest(_manifest(schema))
    assert result.allowed is False
    assert result.code == "invalid_numeric_bounds"
