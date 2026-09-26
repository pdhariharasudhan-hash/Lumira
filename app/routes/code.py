from typing import Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.code.code_service import CodeService
from app.services.response.response_service import (
    build_structured_response
)

router = APIRouter()

code_service = CodeService()


def analyze_code_request(content: str, execute: Dict[str, Any] | None = None) -> Dict[str, Any]:
    text = (content or "").strip()
    execution_payload = execute or {"status": "accept"}

    if not text:
        return {
            "code_target": "fallback_project",
            "files": {"main.py": "print('fallback')"},
            "file_plan": ["main.py"],
            "implementation_steps": ["Generate fallback"],
            "test_steps": ["Run python main.py"],
            "priority": "low",
            "status": "fallback"
        }

    result = code_service.generate(text, execution_payload)

    if not validate_code_output(result):
        return {
            "code_target": "fallback_project",
            "files": {"main.py": "print('fallback')"},
            "file_plan": ["main.py"],
            "implementation_steps": ["Generate fallback"],
            "test_steps": ["Run python main.py"],
            "priority": "low",
            "status": "fallback"
        }

    return result


class CodeRequest(BaseModel):
    input: str
    execute: Dict[str, Any]


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

    return True


@router.post("/code")
def code_endpoint(
    payload: CodeRequest
):

    result = code_service.generate(
        payload.input,
        payload.execute
    )

    if not validate_code_output(
        result
    ):

        result = {
            "code_target": "fallback_project",
            "files": {
                "main.py": "print('fallback')"
            },
            "file_plan": [
                "main.py"
            ],
            "implementation_steps": [
                "Generate fallback"
            ],
            "test_steps": [
                "Run python main.py"
            ],
            "priority": "low",
            "status": "fallback"
        }

    return build_structured_response(
        endpoint="code",
        status="ok",
        data={
            "module": "code",
            "result": result
        }
    )