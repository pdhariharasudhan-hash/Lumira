"""Regression tests for FastAPI parameters used by direct Python callers.

FastAPI query validation belongs in Annotated metadata; Python defaults must
remain ordinary values so unit tests and internal callers don't receive Query
objects instead of the intended default.
"""
import importlib
import inspect

import pytest
from fastapi.params import Query


PARAMETERS = [
    ("app.routes.workflow_insights", "workflow_summary", {"project_id": None}),
    ("app.routes.workflow_insights", "workflow_attention", {"project_id": None, "limit": 20}),
    ("app.routes.goal_intelligence", "get_goal_intelligence", {"project_id": None, "stale_days": 14}),
    ("app.routes.session_insights", "search_sessions", {"q": inspect.Parameter.empty, "status": None, "project_id": None, "limit": 30}),
    ("app.routes.project_insights", "search_projects", {"q": inspect.Parameter.empty, "limit": 30}),
    ("app.routes.goals", "list_goals", {"project_id": None, "parent_goal_id": None, "limit": 100}),
    ("app.routes.devices", "list_devices", {"status": None, "device_type": None, "limit": 100}),
    ("app.routes.memory", "get_relevant_memory", {"q": "", "session_id": None, "project_id": None}),
    ("app.routes.workflows", "list_workflows", {"category": None, "session_id": None, "project_id": None, "goal_id": None}),
    ("app.routes.intelligence", "intelligence_history", {"session_id": None, "project_id": None, "limit": 20}),
    ("app.routes.sessions", "list_sessions", {"limit": 50}),
    ("app.routes.recovery", "list_recovery_runs", {"limit": 50}),
    ("app.routes.run", "list_runs", {"limit": 50}),
    ("app.routes.artifacts", "list_artifacts", {"q": None, "limit": 100, "offset": 0}),
    ("app.routes.search", "search", {"q": inspect.Parameter.empty}),
]


@pytest.mark.parametrize("module_name,function_name,expected_defaults", PARAMETERS)
def test_route_parameters_have_plain_python_defaults(module_name, function_name, expected_defaults):
    module = importlib.import_module(module_name)
    function = getattr(module, function_name)
    signature = inspect.signature(function)

    for parameter_name, expected in expected_defaults.items():
        parameter = signature.parameters[parameter_name]
        if expected is inspect.Parameter.empty:
            assert parameter.default is inspect.Parameter.empty
        else:
            assert parameter.default == expected
        assert not isinstance(parameter.default, Query), (
            f"{module_name}.{function_name}.{parameter_name} exposes a Query object "
            "as its Python default"
        )


@pytest.mark.parametrize("module_name,function_name,expected_defaults", PARAMETERS)
def test_query_constraints_remain_in_annotated_metadata(module_name, function_name, expected_defaults):
    module = importlib.import_module(module_name)
    function = getattr(module, function_name)
    signature = inspect.signature(function)

    for parameter_name in expected_defaults:
        annotation = signature.parameters[parameter_name].annotation
        metadata = getattr(annotation, "__metadata__", ())
        assert any(isinstance(item, Query) for item in metadata), (
            f"{module_name}.{function_name}.{parameter_name} lost its FastAPI Query constraints"
        )
