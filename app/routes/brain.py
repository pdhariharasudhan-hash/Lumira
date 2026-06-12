from fastapi import APIRouter

from app.schemas.common import GenericInput
from app.services.response_service import build_structured_response

# Import engine functions directly
from app.routes.validate import analyze_idea
from app.routes.builder import analyze_build_request
from app.routes.execute import analyze_execution_request
from app.routes.code import analyze_code_request

router = APIRouter()


def main_brain_flow(content: str) -> dict:
    text = content.strip()

    # -------- STEP 1: VALIDATE --------
    validation = analyze_idea(text)

    if validation["verdict"] == "reject":
        return {
            "stage": "validate",
            "status": "stopped",
            "validation": validation
        }

    # -------- STEP 2: BUILD --------
    build = analyze_build_request(text)

    if build["status"] == "refine":
        return {
            "stage": "builder",
            "status": "needs_refinement",
            "validation": validation,
            "builder": build
        }

    # -------- STEP 3: EXECUTE --------
    execution = analyze_execution_request(text)

    if execution["status"] == "refine":
        return {
            "stage": "execute",
            "status": "needs_refinement",
            "validation": validation,
            "builder": build,
            "execute": execution
        }

    # -------- STEP 4: CODE --------
    code = analyze_code_request(text)

    return {
        "stage": "complete",
        "status": "ready_for_build",
        "validation": validation,
        "builder": build,
        "execute": execution,
        "code": code
    }


@router.post("/brain")
def brain_endpoint(payload: GenericInput):
    content = payload.input.strip()

    result = main_brain_flow(content)

    return build_structured_response(
        endpoint="brain",
        status="ok",
        data=result
    )