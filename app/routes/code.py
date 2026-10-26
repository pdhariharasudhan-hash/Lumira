from typing import Dict, Any
import json

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.services.code.code_service import CodeService
from app.services.response.response_service import (
    build_structured_response
)
from app.services.validation.code_validation_service import CodeValidationService

router = APIRouter()

code_service = CodeService()


def analyze_code_request(content: str, execute: Dict[str, Any] | None = None) -> Dict[str, Any]:
    text = (content or "").strip()
    execution_payload = execute or {"status": "reject"}

    if not text:
        return {
            "code_target": None,
            "files": {},
            "file_plan": [],
            "implementation_steps": [],
            "test_steps": [],
            "priority": "low",
            "status": "refine",
            "error": "Provide an accepted execution plan and a non-empty objective.",
        }

    if not isinstance(execution_payload, dict) or execution_payload.get("status") != "accept":
        return {
            "code_target": None,
            "files": {},
            "file_plan": [],
            "implementation_steps": [],
            "test_steps": [],
            "priority": "low",
            "status": "refine",
            "error": "Code generation requires an accepted execution plan.",
        }

    result = code_service.generate(text, execution_payload)

    if not validate_code_output(result):
        return {
            "code_target": None,
            "files": {},
            "file_plan": [],
            "implementation_steps": [],
            "test_steps": [],
            "priority": "low",
            "status": "refine",
            "error": "Code generation did not return a valid project.",
        }

    return result


class CodeRequest(BaseModel):
    input: str = Field(max_length=10000)
    execute: Dict[str, Any]

    @field_validator("execute")
    @classmethod
    def execution_payload_is_bounded(cls, value):
        if len(json.dumps(value, ensure_ascii=False)) > 200_000:
            raise ValueError("execution payload exceeds 200000 characters")
        return value


def validate_code_output(
    result: Dict[str, Any]
) -> bool:

    required_fields = [
        "code_target",
        "files",
        "file_plan",
        "implementation_steps",
        "test_steps",
        "priority",
        "status"
    ]

    for field in required_fields:

        if field not in result:
            return False

    if not isinstance(
        result["files"],
        dict
    ):
        return False

    if len(
        result["files"]
    ) == 0:
        return False

    if result.get("status") != "accept":
        return False

    if not isinstance(result.get("file_plan"), list):
        return False

    if not all(isinstance(path, str) and path in result["files"] for path in result["file_plan"]):
        return False

    return True


@router.post("/code")
def code_endpoint(
    payload: CodeRequest
):

    if payload.execute.get("status") != "accept":
        result = {
            "code_target": None,
            "files": {},
            "file_plan": [],
            "implementation_steps": [],
            "test_steps": [],
            "priority": "low",
            "status": "refine",
            "error": "Code generation requires an accepted execution plan.",
        }
    else:
        result = analyze_code_request(payload.input, payload.execute)

    validation = (
        CodeValidationService().validate(result.get("files", {}))
        if validate_code_output(result)
        else {"valid": False, "errors": [result.get("error", "Code output is invalid.")]}
    )
    if validate_code_output(result) and not validation.get("valid"):
        result["status"] = "refine"
        result["validation"] = validation

    response_status = "ok" if validate_code_output(result) and validation.get("valid") else "refine"

    return build_structured_response(
        endpoint="code",
        status=response_status,
        data={
            "module": "code",
            "result": result
        }
    )
