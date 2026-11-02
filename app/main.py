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


app = FastAPI(
    title="Lumira",
    version="1.0.0",
    description="Personal AI backend for Lumira",
)

register_configured_providers()


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
