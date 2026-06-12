from app.services.planner.planner_service import (
    PlannerService
)

from app.services.builder.builder_service import (
    BuilderService
)

from app.services.execution.execute_service import (
    ExecuteService
)

from app.services.code.code_service import (
    CodeService
)

from app.services.memory.memory_service import (
    MemoryService
)

from app.services.workspace.workspace_service import (
    WorkspaceService
)

from app.services.dashboard.dashboard_service import (
    DashboardService
)


class ServiceRegistry:

    def __init__(
        self
    ):

        self.services = {

            "planner":
            PlannerService(),

            "builder":
            BuilderService(),

            "execute":
            ExecuteService(),

            "code":
            CodeService(),

            "memory":
            MemoryService(),

            "workspace":
            WorkspaceService(),

            "dashboard":
            DashboardService()
        }

    def get(
        self,
        name: str
    ):

        return self.services.get(
            name
        )

    def has(
        self,
        name: str
    ):

        return (
            name
            in
            self.services
        )

    def list_services(
        self
    ):

        return list(
            self.services.keys()
        )