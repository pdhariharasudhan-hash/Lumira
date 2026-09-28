from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.services.devices.device_gateway_service import DeviceGatewayService

router = APIRouter()


class DeviceMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str | None = Field(default=None, max_length=128)
    device_id: str = Field(min_length=1, max_length=128)
    device_type: str = Field(min_length=1, max_length=32)
    message_type: str = Field(min_length=1, max_length=32)
    timestamp: str | None = Field(default=None, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


class DeviceCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_type: str = Field(min_length=1, max_length=32)
    action: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/devices/messages", status_code=202)
def receive_device_message(request: DeviceMessageRequest):
    try:
        result = DeviceGatewayService().receive(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "status": "received", **result}


@router.get("/devices/messages")
def list_device_messages(limit: int = Query(default=50, ge=0, le=200)):
    return {"messages": DeviceGatewayService().list_messages(limit)}


@router.post("/devices/{device_id}/commands")
def send_device_command(device_id: str, request: DeviceCommandRequest):
    result = DeviceGatewayService().send_command(device_id, request.device_type, request.action, request.payload)
    if not result["success"] and result.get("code") == "provider_unavailable":
        raise HTTPException(status_code=501, detail=result)
    if not result["success"] and result.get("code") in {"provider_error", "command_unconfirmed", "invalid_provider_response"}:
        raise HTTPException(status_code=502, detail=result)
    if not result["success"] and result.get("code", "").startswith("invalid_"):
        raise HTTPException(status_code=422, detail=result)
    return result
