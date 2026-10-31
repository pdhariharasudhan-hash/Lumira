from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.services.devices.device_gateway_service import DeviceGatewayService
from app.services.devices.device_registry_service import DeviceRegistryService

router = APIRouter()


class DeviceRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(min_length=1, max_length=128)
    device_type: str = Field(min_length=1, max_length=32)
    capabilities: list[str] = Field(default_factory=list, max_length=30)
    permissions: list[str] = Field(default_factory=list, max_length=20)
    connection: str = Field(default="unverified", max_length=20)
    status: str = Field(default="registered", max_length=20)


class DeviceStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(min_length=1, max_length=20)


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


@router.post("/devices/register")
def register_device(request: DeviceRegisterRequest):
    try:
        return {"success": True, "device": DeviceRegistryService().register_device(
            request.device_id, request.device_type, request.capabilities,
            request.permissions, request.connection, request.status
        )}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/devices")
def list_devices(
    status: str | None = Query(default=None, max_length=20),
    device_type: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=100, ge=0, le=200),
):
    try:
        return {"devices": DeviceRegistryService().list_devices(status, device_type, limit)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/devices/{device_id}/status")
def update_device_status(device_id: str, request: DeviceStatusUpdate):
    try:
        return {"success": True, "device": DeviceRegistryService().update_status(device_id, request.status)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="device not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/devices/messages", status_code=202)
def receive_device_message(request: DeviceMessageRequest):
    try:
        result = DeviceGatewayService().receive(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        if result.get("duplicate") is True:
            registry_status = "duplicate_ignored"
        else:
            registry_updated = DeviceRegistryService().record_message_seen(request.device_id, request.device_type)
            registry_status = "updated" if registry_updated else "unregistered_or_type_mismatch"
    except Exception:
        # Message persistence already succeeded; expose secondary registry failure
        # without claiming that device presence was updated.
        registry_status = "update_failed"
    return {"success": True, "status": "received", "registry_status": registry_status, **result}


@router.get("/devices/messages")
def list_device_messages(limit: int = Query(default=50, ge=0, le=200)):
    return {"messages": DeviceGatewayService().list_messages(limit)}


@router.get("/devices/summary")
def device_summary():
    try:
        devices = DeviceRegistryService().list_devices(limit=200)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Device registry is unavailable") from exc
    by_status = {}
    by_type = {}
    for device in devices:
        by_status[device.get("status", "unknown")] = by_status.get(device.get("status", "unknown"), 0) + 1
        by_type[device.get("device_type", "unknown")] = by_type.get(device.get("device_type", "unknown"), 0) + 1
    return {"success": True, "total": len(devices), "by_status": by_status, "by_type": by_type}


@router.post("/devices/{device_id}/commands")
def send_device_command(device_id: str, request: DeviceCommandRequest):
    try:
        registry = DeviceRegistryService()
        registered = next(
            (item for item in registry.list_devices(limit=200) if item.get("device_id") == device_id),
            None,
        )
        fresh_heartbeat = registry.is_recently_seen(device_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Device registry is unavailable; command was not sent") from exc
    if registered is None:
        raise HTTPException(status_code=404, detail="Device must be registered before commands can be sent")
    if registered.get("device_type") != request.device_type:
        raise HTTPException(status_code=422, detail="Device type does not match its registered type")
    if "commands.receive" not in registered.get("permissions", []):
        raise HTTPException(status_code=403, detail="Device has not granted the commands.receive permission")
    if registered.get("status") != "online" or not fresh_heartbeat:
        raise HTTPException(status_code=409, detail="Device has no fresh heartbeat/message within 120 seconds; command was not sent")
    result = DeviceGatewayService().send_command(device_id, request.device_type, request.action, request.payload)
    if not result["success"] and result.get("code") == "provider_unavailable":
        raise HTTPException(status_code=501, detail=result)
    if not result["success"] and result.get("code") in {"provider_error", "command_unconfirmed", "invalid_provider_response"}:
        raise HTTPException(status_code=502, detail=result)
    if not result["success"] and result.get("code", "").startswith("invalid_"):
        raise HTTPException(status_code=422, detail=result)
    return result
