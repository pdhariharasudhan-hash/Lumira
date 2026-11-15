from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.workspace.project_terminal_service import ProjectTerminalService
from app.services.workspace.sandbox_provider_factory import create_sandbox_provider

router = APIRouter()
# Inject the concrete platform provider into the terminal service. Execution
# remains hard-disabled until the independent OS-sandbox acceptance gate passes.
service = ProjectTerminalService(sandbox=create_sandbox_provider())


class TerminalRequest(BaseModel):
    project: str = Field(min_length=1, max_length=100)
    version: str = Field(pattern=r"^v[1-9][0-9]{0,8}$")
    command_id: str = Field(min_length=1, max_length=40)
    trusted_project: bool = False


@router.get("/projects/{project}/{version}/terminal/commands")
def terminal_commands(project: str, version: str):
    return {"success": True, "commands": service.list_commands()}


@router.post("/projects/{project}/{version}/terminal/run")
def terminal_run(project: str, version: str, payload: TerminalRequest):
    if payload.project != project or payload.version != version:
        return {"success": False, "code": "path_mismatch", "message": "Project path and payload must match."}
    return service.run(
        project,
        version,
        payload.command_id,
        trusted_project=payload.trusted_project,
    )


@router.get("/projects/{project}/{version}/terminal/runs")
def terminal_runs(project: str, version: str):
    return {"success": True, "runs": service.list_runs(project, version)}
