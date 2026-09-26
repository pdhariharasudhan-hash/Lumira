from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

from app.routes.brain import (
    router as brain_router
)

from app.routes.run import (
    router as run_router
)

from app.routes.projects import (
    router as projects_router
)

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

from app.routes.command import (
    router as command_router
)

from app.routes.sessions import (
    router as sessions_router
)

from app.routes.goals import (
    router as goals_router
)


app = FastAPI(
    title="Personal AI Core",
    version="1.0.0",
    description=
    "Simple FastAPI backend MVP for Personal AI Core"
)


app.mount(
    "/static",
    StaticFiles(
        directory="app/frontend"
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

app.include_router(
    brain_router,
    tags=["Brain"]
)

app.include_router(
    run_router,
    tags=["Run"]
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
    command_router,
    tags=["Command"]
)

app.include_router(
    sessions_router,
    tags=["Sessions"]
)

app.include_router(
    goals_router,
    tags=["Goals"]
)


@app.get("/")
def root():

    return FileResponse(
        "app/frontend/index.html"
    )