from app.core.lumira_core import (
    LumiraCore
)

from app.agents.code_agent import (
    CodeAgent
)

from app.services.workspace.workspace_service import (
    WorkspaceService
)


class WorkflowStepRouter:

    def __init__(
        self
    ):

        self.core = (
            LumiraCore()
        )

        self.code_agent = (
            CodeAgent()
        )

        self.workspace = (
            WorkspaceService()
        )

    def execute_step(
        self,
        step: str,
        goal: str
    ):

        if step == "validate":

            return {

                "step":
                step,

                "status":
                "completed"
            }

        if step == "builder":

            return (
                self.core.build(
                    goal
                )
            )

        if step == "execute":

            return (
                self.core.execute(
                    goal
                )
            )

        if step == "code":

            return (
                self.code_agent.execute(
                    goal
                )
            )

        if step == "save_project":

            project_name = (
                goal.lower()
                .replace(
                    "build",
                    ""
                )
                .replace(
                    "api",
                    ""
                )
                .strip()
                .replace(
                    " ",
                    "_"
                )
            )

            return (

                self.workspace
                .add_project(

                    project_name=
                    project_name,

                    project_path=
                    f"generated/{project_name}"
                )
            )

        return {

            "step":
            step,

            "status":
            "unknown"
        }