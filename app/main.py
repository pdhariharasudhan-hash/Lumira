

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from urllib.parse import urlsplit
from pathlib import Path

from app.routes.builder import (
    router as builder_router
)

from app.routes.code import (
    router as code_router
)

from app.routes.execute import (
    router as execute_router
)

from app.routes.validate import (
    router as validate_router
)

from app.routes.memory import (
    router as memory_router
)

from app.routes.health import (
    router as health_router
)

from app.routes.resources import router as resources_router

from app.routes.brain import (
    router as brain_router
)

from app.routes.run import (
    router as run_router
)

from app.routes.projects import (
    router as projects_router
)
from app.routes.project_insights import router as project_insights_router

from app.routes.project_details import (
    router as project_details_router
)

from app.routes.continue_project import (
    router as continue_router
)

from app.routes.compare import (
    router as compare_router
)

from app.routes.project_versions import (
    router as project_versions_router
)

from app.routes.project_files import (
    router as project_files_router
)

from app.routes.project_file_content import (
    router as project_file_content_router
)

from app.routes.search import (
    router as search_router
)

from app.routes.voice_capture import (
    router as voice_capture_router
)

from app.routes.artifacts import (
    router as artifacts_router
)

from app.routes.command import (
    router as command_router
)

from app.routes.sessions import (
    router as sessions_router
)
from app.routes.session_insights import router as session_insights_router

from app.routes.goals import (
    router as goals_router
)
from app.routes.goal_intelligence import router as goal_intelligence_router

from app.routes.agents import router as agents_router
from app.routes.workflows import router as workflows_router
from app.routes.workflow_insights import router as workflow_insights_router
from app.routes.auth import router as auth_router
from app.routes.devices import router as devices_router
from app.routes.project_terminal import router as project_terminal_router
from app.routes.project_preview import router as project_preview_router
from app.routes.web import router as web_router
from app.routes.recovery import router as recovery_router
from app.routes.features import router as features_router
from app.routes.intelligence import router as intelligence_router
from app.routes.notepad import router as notepad_router
from app.routes.image_understanding import router as image_understanding_router
from app.routes.image_generation import router as image_generation_router
from app.routes.research_library import router as research_library_router
from app.routes.recovery_checkpoints import router as recovery_checkpoints_router
from app.routes.personal_context import router as personal_context_router
from app.routes.knowledge import router as knowledge_router
from app.routes.system_status import router as system_status_router
from app.routes.core_features import router as core_features_router
from app.routes.core_runtime import router as core_runtime_router
from app.routes.reminders import router as reminders_router
from app.routes.notifications import router as notifications_router
from app.routes.quick_tasks import router as quick_tasks_router
from app.routes.core_events import router as core_events_router
import ipaddress

from app.services.auth.local_auth_service import LocalAuthService
from app.services.providers.startup_registration import register_configured_providers


app = FastAPI(
    title="Personal AI Core",
    version="1.0.0",
    description=
    "Simple FastAPI backend MVP for Personal AI Core"
)

register_configured_providers()


@app.middleware("http")
async def local_auth_boundary(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    # Loopback-only API access is not sufficient protection against browser
    # CSRF: a hostile website can make requests to localhost from the user's
    # browser. Accept browser-origin requests only from local workbench origins.
    origin = request.headers.get("origin")
    if origin:
        try:
            parsed_origin = urlsplit(origin)
            origin_port = parsed_origin.port  # Validate malformed and out-of-range ports.
            trusted_origin = (
                parsed_origin.scheme in {"http", "https"}
                and parsed_origin.hostname in {"localhost", "127.0.0.1", "::1"}
                and origin_port in {5000, 8000}
                and parsed_origin.username is None
                and parsed_origin.password is None
                and not parsed_origin.path
                and not parsed_origin.query
                and not parsed_origin.fragment
            )
        except ValueError:
            trusted_origin = False
        if not trusted_origin:
            return JSONResponse(
                status_code=403,
                content={"detail": "Untrusted browser origin"},
            )

    client_host = request.client.host if request.client else ""
    try:
        loopback = ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        loopback = client_host in {"testclient", "localhost"}
    authorization = request.headers.get("authorization", "")
    principal = None
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse(status_code=401, content={"detail": "Valid Bearer authentication is required"}, headers={"WWW-Authenticate": "Bearer"})
        principal = LocalAuthService().verify(token)
        if principal is None:
            return JSONResponse(status_code=401, content={"detail": "Valid Bearer authentication is required"}, headers={"WWW-Authenticate": "Bearer"})
    elif not loopback:
        return JSONResponse(status_code=401, content={"detail": "Valid Bearer authentication is required"}, headers={"WWW-Authenticate": "Bearer"})
    request.state.principal = principal or {"subject": "local", "owner_id": "local", "authentication": "loopback"}
    return await call_next(request)


app.mount(
    "/static",
    StaticFiles(
        directory=str(Path(__file__).resolve().parent / "frontend")
    ),
    name="static"
)


app.include_router(
    builder_router,
    tags=["Builder"]
)

app.include_router(
    code_router,
    tags=["Code"]
)

app.include_router(
    execute_router,
    tags=["Execute"]
)

app.include_router(
    validate_router,
    tags=["Validate"]
)

app.include_router(
    memory_router,
    tags=["Memory"]
)

app.include_router(
    health_router
)

app.include_router(resources_router)

app.include_router(
    brain_router,
    tags=["Brain"]
)

app.include_router(
    run_router,
    tags=["Run"]
)

app.include_router(
    project_insights_router,
    tags=["Project Insights"]
)

app.include_router(
    projects_router,
    tags=["Projects"]
)

app.include_router(
    project_details_router,
    tags=["Project Details"]
)

app.include_router(
    continue_router,
    tags=["Continue"]
)

app.include_router(
    compare_router,
    tags=["Compare"]
)

app.include_router(
    project_versions_router,
    tags=["Project Versions"]
)

app.include_router(
    project_files_router,
    tags=["Project Files"]
)

app.include_router(
    project_file_content_router,
    tags=["Project File Content"]
)

app.include_router(
    search_router,
    tags=["Search"]
)

app.include_router(
    voice_capture_router,
    tags=["Voice Capture"]
)

app.include_router(
    artifacts_router,
    tags=["Artifacts"]
)

app.include_router(
    command_router,
    tags=["Command"]
)

app.include_router(
    session_insights_router,
    tags=["Session Insights"]
)

app.include_router(
    sessions_router,
    tags=["Sessions"]
)

app.include_router(
    goals_router,
    tags=["Goals"]
)

app.include_router(
    goal_intelligence_router,
    tags=["Goal Intelligence"]
)

app.include_router(
    agents_router,
    tags=["Agents"]
)

app.include_router(
    workflow_insights_router,
    tags=["Workflow Insights"]
)

app.include_router(
    workflows_router,
    tags=["Workflows"]
)

app.include_router(
    auth_router,
    tags=["Authentication"]
)

app.include_router(
    devices_router,
    tags=["Device Gateway"]
)

app.include_router(
    project_terminal_router,
    tags=["Project Terminal"]
)

app.include_router(
    project_preview_router,
    tags=["Project Preview"]
)

app.include_router(
    web_router,
    tags=["Web Access"]
)

app.include_router(
    recovery_router,
    tags=["Workflow Recovery"]
)

app.include_router(
    features_router,
    tags=["Features"]
)

app.include_router(
    intelligence_router,
    tags=["Intelligence and Modes"]
)

app.include_router(
    notepad_router,
    tags=["Notepad"]
)

app.include_router(
    image_understanding_router,
    tags=["Image Understanding"]
)

app.include_router(
    image_generation_router,
    tags=["Image Generation"]
)

app.include_router(
    research_library_router,
    tags=["Research Library"]
)

app.include_router(
    recovery_checkpoints_router,
    tags=["Recovery Checkpoints"]
)

app.include_router(
    personal_context_router,
    tags=["Personal Context"]
)

app.include_router(knowledge_router)
app.include_router(system_status_router)
app.include_router(core_features_router)
app.include_router(core_runtime_router)
app.include_router(reminders_router, tags=["Reminders"])
app.include_router(notifications_router, tags=["Notifications"])
app.include_router(quick_tasks_router, tags=["Quick Tasks"])
app.include_router(core_events_router, tags=["Core Events"])


@app.get("/")
def root():

    return FileResponse(
        "app/frontend/index.html"
    )
