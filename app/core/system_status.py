from app.core.service_registry import (
    ServiceRegistry
)


class SystemStatus:

    def __init__(
        self,
        registry=None,
        health_service=None,
    ):

        self.registry = registry if registry is not None else ServiceRegistry()
        self.health_service = health_service

    def get_status(
        self
    ):

        services = self.registry.list_services()
        try:
            health_service = self.health_service
            if health_service is None:
                from app.services.system.system_health_service import SystemHealthService

                health_service = SystemHealthService()
            snapshot = health_service.snapshot()
        except Exception:
            snapshot = None

        checks = snapshot.get("checks") if isinstance(snapshot, dict) else None
        valid_checks = isinstance(checks, dict) and bool(checks) and all(
            isinstance(name, str)
            and bool(name)
            and isinstance(check, dict)
            and check.get("status") in ("healthy", "degraded")
            for name, check in checks.items()
        )
        valid_snapshot = (
            isinstance(snapshot, dict)
            and snapshot.get("success") is True
            and snapshot.get("status") in ("healthy", "degraded")
            and valid_checks
        )

        if valid_snapshot:
            degraded = snapshot.get("degraded_subsystems")
            degraded = (
                [name for name in degraded if isinstance(name, str)]
                if isinstance(degraded, list)
                else []
            )
            degraded.extend(
                name
                for name, check in checks.items()
                if check["status"] == "degraded" and name not in degraded
            )
            health = "degraded" if snapshot["status"] == "degraded" or degraded else "healthy"
            timestamp = snapshot.get("timestamp")
            timestamp = timestamp if isinstance(timestamp, str) else None
        else:
            health = "degraded"
            checks = {"system_health_service": {"status": "degraded", "error": "health_probe_failed"}}
            degraded = ["system_health_service"]
            timestamp = None

        return {

            "services":
            services,

            "service_count":
            len(services),

            "health":
            health,

            "checks": checks,

            "degraded_subsystems": degraded,

            "health_timestamp": timestamp,
        }
