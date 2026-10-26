from app.core.service_registry import (
    ServiceRegistry
)


class SystemStatus:

    def __init__(
        self
    ):

        self.registry = (
            ServiceRegistry()
        )

    def get_status(
        self
    ):

        return {

            "services":
            self.registry.list_services(),

            "service_count":
            len(
                self.registry.list_services()
            ),

            "health":
            "healthy"
        }