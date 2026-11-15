from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
import ipaddress
import json

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.router_registry import register_routes
from app.core.output import annotate_json_payload
from app.services.auth.local_auth_service import LocalAuthService
from app.services.providers.startup_registration import register_configured_providers
from app.services.plugins.plugin_runtime_service import PluginRuntimeService
from app.services.system.application_lifecycle_service import (
    ApplicationLifecycleManager,
    LifecycleError,
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Own optional provider initialization and lifecycle state per app instance."""
    lifecycle = ApplicationLifecycleManager()
    lifecycle.register(
        "optional_providers",
        register_configured_providers,
        priority=100,
    )
    from app.services.multi_model.startup_registration import register_configured_chat_models
    lifecycle.register(
        "multi_model_providers",
        register_configured_chat_models,
        priority=110,
    )
    from app.services.system.managed_scheduled_worker_service import ManagedScheduledWorkerService
    scheduled_worker = ManagedScheduledWorkerService()
    lifecycle.register(
        "managed_scheduled_worker",
        scheduled_worker.start,
        scheduled_worker.stop,
        priority=200,
    )
    application.state.managed_scheduled_worker = scheduled_worker
    application.state.lifecycle_manager = lifecycle
    try:
        application.state.plugin_runtime = PluginRuntimeService()
        application.state.plugin_runtime_error = None
    except Exception as exc:
        # A corrupt or unavailable plugin registry disables only the plugin
        # subsystem; the core personal AI runtime remains available.
        application.state.plugin_runtime = None
        application.state.plugin_runtime_error = type(exc).__name__
    await lifecycle.startup()
    # Recover jobs left in the running state by the previous process. Queued
    # tasks are durable pending work and must not be marked interrupted.
    from app.services.background_tasks.background_agent_task_service import BackgroundAgentTaskService
    application.state.background_task_recovery = BackgroundAgentTaskService().recover_interrupted()
    try:
        yield
    finally:
        await lifecycle.shutdown()


app = FastAPI(
    title="Lumira",
    version="1.0.0",
    description="Personal AI backend for Lumira",
    lifespan=lifespan,
)


@app.middleware("http")
async def lifecycle_work_tracking(request: Request, call_next):
    """Track requests so application shutdown drains active work first."""
    lifecycle = getattr(request.app.state, "lifecycle_manager", None)
    if lifecycle is None:
        return await call_next(request)
    try:
        async with lifecycle.track_work():
            return await call_next(request)
    except LifecycleError:
        return JSONResponse(
            status_code=503,
            content={"detail": "Application is shutting down; retry the request."},
            headers={"Retry-After": "1"},
        )


def _annotate_response(response):
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type or not getattr(response, "body", None):
        return response
    try:
        payload = json.loads(response.body)
    except (TypeError, ValueError):
        return response
    annotated = annotate_json_payload(payload)
    if annotated != payload:
        response.body = json.dumps(annotated, ensure_ascii=False).encode("utf-8")
        response.headers["content-length"] = str(len(response.body))
    return response


@app.middleware("http")
async def local_auth_boundary(request: Request, call_next):
    if request.url.path == "/health":
        return _annotate_response(await call_next(request))

    origin = request.headers.get("origin")
    if origin:
        try:
            parsed_origin = urlsplit(origin)
            origin_port = parsed_origin.port
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
            return JSONResponse(status_code=403, content={"detail": "Untrusted browser origin"})

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
            return JSONResponse(
                status_code=401,
                content={"detail": "Valid Bearer authentication is required"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        principal = LocalAuthService().verify(token)
        if principal is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Valid Bearer authentication is required"},
                headers={"WWW-Authenticate": "Bearer"},
            )
    elif not loopback:
        return JSONResponse(
            status_code=401,
            content={"detail": "Valid Bearer authentication is required"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    request.state.principal = principal or {
        "subject": "local",
        "owner_id": "local",
        "authentication": "loopback",
    }
    return _annotate_response(await call_next(request))


app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).resolve().parent / "frontend")),
    name="static",
)

register_routes(app)


@app.get("/")
def root():
    return FileResponse("app/frontend/index.html")
