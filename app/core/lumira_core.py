from app.core.service_registry import (
    ServiceRegistry
)

from app.core.system_status import (
    SystemStatus
)


class LumiraCore:

    def __init__(
        self
    ):

        self.registry = (
            ServiceRegistry()
        )

        self.system_status = (
            SystemStatus()
        )

    def plan(
        self,
        goal: str
    ):

        planner = (
            self.registry.get(
                "planner"
            )
        )

        return planner.create_plan(
            goal
        )

    def build(
        self,
        goal: str
    ):

        builder = (
            self.registry.get(
                "builder"
            )
        )

        return builder.build(
            goal
        )

    def execute(
        self,
        goal: str
    ):

        builder = self.build(
            goal
        )

        executor = (
            self.registry.get(
                "execute"
            )
        )

        return executor.execute(
            goal,
            builder
        )

    def generate(
        self,
        goal: str
    ):

        execution = self.execute(
            goal
        )

        code = (
            self.registry.get(
                "code"
            )
        )

        return code.generate(
            goal,
            execution
        )

    def run(
        self,
        goal: str
    ):

        builder = self.build(
            goal
        )

        execution = self.execute(
            goal
        )

        code = self.generate(
            goal
        )

        return {

            "success":
            True,

            "goal":
            goal,

            "builder":
            builder,

            "execution":
            execution,

            "code":
            code
        }

    def status(
        self
    ):

        return (
            self.system_status
            .get_status()
        )