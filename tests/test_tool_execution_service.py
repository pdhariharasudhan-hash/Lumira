import asyncio

import pytest

from app.services.brain.tool_execution_policy_service import (
    ToolApprovalService,
    ToolExecutionBudget,
    ToolExecutionPolicyService,
)
from app.services.brain.tool_execution_service import ToolExecutionService


def _manifest(capability="notes.read", requires_approval=False):
    return {
        "name": "read_note",
        "capability": capability,
        "requires_approval": requires_approval,
        "parameters": {
            "type": "object",
            "properties": {"note_id": {"type": "string", "minLength": 1}},
            "required": ["note_id"],
            "additionalProperties": False,
        },
    }


def test_executor_runs_only_registered_async_tools_with_explicit_capability():
    async def read_note(args):
        return {"note_id": args["note_id"], "content": "hello"}

    executor = ToolExecutionService(ToolExecutionPolicyService({"notes.read": True}))
    executor.register(_manifest(), read_note)
    result = asyncio.run(executor.execute("read_note", {"note_id": "n1"}, session_id="s1"))
    assert result["success"] is True
    assert result["result"]["content"] == "hello"
    assert executor.list_tools() == ["read_note"]


def test_executor_denies_missing_permission_and_invalid_arguments_without_calling_handler():
    called = []

    async def handler(args):
        called.append(args)
        return {"ok": True}

    executor = ToolExecutionService()
    executor.register(_manifest(), handler)
    denied = asyncio.run(executor.execute("read_note", {"note_id": "n1"}, session_id="s1"))
    invalid = asyncio.run(executor.execute("read_note", {"unexpected": True}, session_id="s1"))
    assert denied["code"] == "permission_denied"
    assert invalid["code"] == "permission_denied"
    assert called == []


def test_high_risk_execution_requires_exact_single_use_explicit_approval():
    async def delete_file(args):
        return {"deleted": args["path"]}

    manifest = {
        "name": "delete_file",
        "capability": "filesystem.delete",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "minLength": 1}},
            "required": ["path"],
            "additionalProperties": False,
        },
    }
    approvals = ToolApprovalService()
    executor = ToolExecutionService(
        ToolExecutionPolicyService({"filesystem.delete": True}), approvals
    )
    executor.register(manifest, delete_file)
    args = {"path": "workspace/tmp.txt"}
    assert asyncio.run(executor.execute("delete_file", args, session_id="s1"))["code"] == "approval_required"
    rejected = executor.grant_approval(
        session_id="s1", tool_name="delete_file", arguments=args, user_confirmed=False
    )
    assert rejected["code"] == "explicit_confirmation_required"
    grant = executor.grant_approval(
        session_id="s1", tool_name="delete_file", arguments=args, user_confirmed=True
    )
    assert grant["success"] is True
    result = asyncio.run(executor.execute(
        "delete_file", args, session_id="s1", approval_id=grant["approval_id"]
    ))
    assert result["success"] is True
    replay = asyncio.run(executor.execute(
        "delete_file", args, session_id="s1", approval_id=grant["approval_id"]
    ))
    assert replay["code"] == "approval_missing_or_consumed"


def test_executor_rejects_sync_handlers_and_duplicate_names():
    async def handler(args):
        return args

    executor = ToolExecutionService(ToolExecutionPolicyService({"notes.read": True}))
    with pytest.raises(TypeError, match="async"):
        executor.register(_manifest(), lambda args: args)
    executor.register(_manifest(), handler)
    with pytest.raises(ValueError, match="already registered"):
        executor.register(_manifest(), handler)
    assert executor.unregister("read_note") is True
    assert executor.unregister("read_note") is False


def test_executor_bounds_runtime_and_sanitizes_handler_errors():
    async def slow(args):
        await asyncio.sleep(0.05)
        return {"ok": True}

    async def broken(args):
        raise RuntimeError("private provider secret")

    executor = ToolExecutionService(ToolExecutionPolicyService({"notes.read": True}))
    executor.register(_manifest(), slow)
    timeout = asyncio.run(executor.execute(
        "read_note", {"note_id": "n1"}, session_id="s1",
        budget=ToolExecutionBudget(timeout_seconds=0.005),
    ))
    assert timeout["code"] == "tool_execution_timeout"

    executor.unregister("read_note")
    executor.register(_manifest(), broken)
    failed = asyncio.run(executor.execute("read_note", {"note_id": "n1"}, session_id="s1"))
    assert failed == {
        "success": False, "code": "tool_execution_failed", "error_type": "RuntimeError"
    }
    assert "private provider secret" not in str(failed)


def test_executor_bounds_result_and_cumulative_budget():
    async def large(args):
        return {"payload": "x" * 140_000}

    executor = ToolExecutionService(ToolExecutionPolicyService({"notes.read": True}))
    executor.register(_manifest(), large)
    result = asyncio.run(executor.execute("read_note", {"note_id": "n1"}, session_id="s1"))
    assert result["code"] == "tool_result_too_large"

    async def small(args):
        return {"ok": True}

    executor.unregister("read_note")
    executor.register(_manifest(), small)
    budget = ToolExecutionBudget(max_total_result_bytes=1)
    bounded = asyncio.run(executor.execute(
        "read_note", {"note_id": "n1"}, session_id="s1", budget=budget
    ))
    assert bounded["code"] == "execution_result_budget_exceeded"
