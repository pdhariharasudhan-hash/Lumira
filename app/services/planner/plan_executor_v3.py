from app.services.builder.builder_service import (
    BuilderService
)

from app.services.execution.execute_service import (
    ExecuteService
)

from app.services.execution.execution_session_service import (
    ExecutionSessionService
)

from app.services.code.code_service import (
    CodeService
)


class PlanExecutorV3:

    def execute(
        self,
        goal: str
    ):

        builder = (
            BuilderService()
            .build(
                goal
            )
        )

        execution = (
            ExecuteService()
            .execute(
                goal,
                builder
            )
        )

        code = (
            CodeService()
            .generate(
                goal,
                execution
            )
        )

        session = (
            ExecutionSessionService()
            .create_session(
                goal,
                builder,
                execution,
                code
            )
        )

        return {

            "success":
            True,

            "goal":
            goal,

            "session":
            session,

            "builder":
            builder,

            "execution":
            execution,

            "code":
            code
        }