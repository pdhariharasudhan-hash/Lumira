from collections.abc import Mapping
from threading import RLock
from typing import Any

from app.services.planner.planner_service import PlannerService
from app.services.builder.builder_service import BuilderService
from app.services.execution.execute_service import ExecuteService
from app.services.code.code_service import CodeService
from app.services.memory.memory_service import MemoryService
from app.services.workspace.workspace_service import WorkspaceService
from app.services.dashboard.dashboard_service import DashboardService


class ServiceRegistry:
    """Thread-safe registry for Lumira services.

    The default constructor preserves the historical seven-service setup.
    Tests and embedded runtimes can inject a custom mapping with
    `include_defaults=False` to avoid constructing production services.
    """

    def __init__(
        self,
        services: Mapping[str, Any] | None = None,
        *,
        include_defaults: bool = True,
    ) -> None:
        self._lock = RLock()
        self.services: dict[str, Any] = {}

        if include_defaults:
            self.services.update(
                {
                    "planner": PlannerService(),
                    "builder": BuilderService(),
                    "execute": ExecuteService(),
                    "code": CodeService(),
                    "memory": MemoryService(),
                    "workspace": WorkspaceService(),
                    "dashboard": DashboardService(),
                }
            )

        if services is not None:
            if include_defaults and set(services).intersection(self.services):
                duplicates = sorted(set(services).intersection(self.services))
                raise ValueError(
                    "Injected services conflict with default registrations: "
                    + ", ".join(duplicates)
                )
            for name, service in services.items():
                self.register(name, service)

    @staticmethod
    def _validate_name(name: str) -> str:
        if not isinstance(name, str):
            raise TypeError("service name must be a string")
        normalized = name.strip()
        if not normalized:
            raise ValueError("service name must not be empty")
        return normalized

    def register(self, name: str, service: Any, *, replace: bool = False) -> Any:
        """Register a service, rejecting accidental replacement by default."""
        normalized = self._validate_name(name)
        if service is None:
            raise ValueError("service must not be None")

        with self._lock:
            if normalized in self.services and not replace:
                raise ValueError(f"service already registered: {normalized}")
            self.services[normalized] = service
        return service

    def unregister(self, name: str) -> Any:
        """Remove and return a service; missing names raise KeyError."""
        normalized = self._validate_name(name)
        with self._lock:
            return self.services.pop(normalized)

    def get(self, name: str) -> Any | None:
        normalized = self._validate_name(name)
        with self._lock:
            return self.services.get(normalized)

    def has(self, name: str) -> bool:
        normalized = self._validate_name(name)
        with self._lock:
            return normalized in self.services

    def list_services(self) -> list[str]:
        with self._lock:
            return list(self.services.keys())
