from fastapi import APIRouter, HTTPException, Request
from urllib.parse import urlsplit
import ipaddress

from app.services.auth.local_auth_service import LocalAuthService

router = APIRouter()


@router.post("/auth/local-token")
def issue_local_token(request: Request):
    client_host = request.client.host if request.client else ""
    try:
        local_client = ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        local_client = client_host in {"testclient", "localhost"}
    if not local_client:
        raise HTTPException(status_code=403, detail="Local token bootstrap is available only from loopback")
    origin = request.headers.get("origin")
    if origin:
        origin_host = urlsplit(origin).hostname
        if origin_host not in {"localhost", "127.0.0.1", "::1"}:
            raise HTTPException(status_code=403, detail="Local token bootstrap origin is not trusted")
    return LocalAuthService().issue_local_token()
