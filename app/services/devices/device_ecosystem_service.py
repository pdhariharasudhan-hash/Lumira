"""Device ecosystem inventory and safe capability planning (no discovery or commands)."""
from app.services.devices.device_registry_service import DeviceRegistryService
from app.services.devices.device_profile_service import DeviceProfileService
from app.services.providers.provider_registry import ProviderRegistry


class DeviceEcosystemService:
    LOCAL_TYPES = {"laptop", "raspberry_pi", "raspberry_pi_pico", "esp32", "arduino", "robotics", "cyberdeck", "smart_glasses", "sensor", "camera", "microphone", "drone", "wearable", "smart_display", "printer"}
    NETWORK_TYPES = {"wifi", "bluetooth", "mobile", "smart_home", "vehicle"}

    def __init__(self, registry=None, profiles=None):
        self.registry = registry or DeviceRegistryService()
        self.profiles = profiles or DeviceProfileService()

    def overview(self):
        devices = self.registry.list_devices(limit=200)
        profiles = self.profiles.list()
        profile_index = {item.get("profile_id"): item for item in profiles}
        items, connections, types = [], {}, {}
        for device in devices:
            device_type = device.get("device_type", "unknown")
            connection = device.get("connection", "unverified")
            types[device_type] = types.get(device_type, 0) + 1
            connections[connection] = connections.get(connection, 0) + 1
            try:
                fresh = self.registry.is_recently_seen(device.get("device_id", ""))
            except Exception:
                fresh = False
            items.append({**device, "heartbeat_fresh": fresh,
                          "effective_status": "online" if fresh else "offline_or_stale",
                          "profile": profile_index.get(device.get("device_id"))})
        return {"success": True, "devices": items, "profiles": profiles,
                "summary": {"registered_devices": len(devices), "profiles": len(profiles),
                            "fresh_devices": sum(1 for x in items if x["heartbeat_fresh"]),
                            "stale_or_offline": sum(1 for x in items if not x["heartbeat_fresh"]),
                            "by_type": types, "by_connection": connections},
                "transport": {"configured": ProviderRegistry.get("device_transport") is not None,
                              "note": "A configured adapter is required for physical discovery and command delivery."},
                "scope": "Inventory is based on explicitly registered devices and profiles; no nearby-device scan is performed."}

    def plan(self, device_id: str, capability: str):
        if not isinstance(device_id, str) or not device_id.strip() or len(device_id) > 128:
            raise ValueError("device_id must contain 1-128 characters")
        if not isinstance(capability, str) or not capability.strip() or len(capability) > 80:
            raise ValueError("capability must contain 1-80 characters")
        device = next((x for x in self.registry.list_devices(limit=200) if x.get("device_id") == device_id), None)
        if device is None:
            return {"success": False, "code": "device_not_registered", "device_id": device_id}
        granted = set(device.get("capabilities", []))
        permissions = set(device.get("permissions", []))
        fresh = self.registry.is_recently_seen(device_id)
        has_capability = capability in granted
        required_permission = capability if capability in {"telemetry.read", "camera.capture", "microphone.capture", "robot.motion", "smart_home.control", "vehicle.read", "files.read", "files.write"} else "commands.receive"
        has_permission = required_permission in permissions
        transport = ProviderRegistry.get("device_transport")
        transport_ready = transport is not None
        if transport_ready and callable(getattr(transport, "is_device_configured", None)):
            try:
                transport_ready = bool(transport.is_device_configured(device_id, device.get("device_type", "")))
            except Exception:
                transport_ready = False
        return {"success": True, "device_id": device_id, "capability": capability,
                "eligible": bool(fresh and has_capability and has_permission and transport_ready),
                "checks": {"registered": True, "heartbeat_fresh": fresh,
                           "capability_declared": has_capability,
                           "required_permission": required_permission,
                           "permission_granted": has_permission,
                           "transport_configured": transport_ready},
                "recommended_mode": "local" if device.get("device_type") in self.LOCAL_TYPES else "hybrid",
                "next_step": "Use an explicitly configured device adapter only after all readiness checks pass.",
                "command_sent": False}
