from app.core.lumira_core import (
    LumiraCore
)

from app.agents.code_agent import (
    CodeAgent
)

from app.services.workspace.workspace_service import (
    WorkspaceService
)

from app.services.project_context.project_manager_service import (
    ProjectManagerService
)

from app.services.projects.project_writer import (
    ProjectWriter
)

from app.services.validation.code_validation_service import (
    CodeValidationService
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

        self.project_manager = (
            ProjectManagerService()
        )

        self.validator = (
            CodeValidationService()
        )

    def execute_step(
        self,
        step: str,
        goal: str,
        context: dict
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

            code_result = (
                context.get(
                    "code",
                    {}
                )
            )

            project_name = (
                code_result.get(
                    "code_target"
                )
            )

            project_files = (
                code_result.get(
                    "files",
                    {}
                )
            )

            if not project_name:

                return {

                    "success":
                    False,

                    "message":
                    "code_target missing"
                }

            validation = (

                self.validator
                .validate(
                    project_files
                )
            )

            if not validation[
                "valid"
            ]:

                return {

                    "success":
                    False,

                    "message":
                    "code validation failed",

                    "errors":
                    validation[
                        "errors"
                    ]
                }

            self.project_manager.create_project(

                project_name=
                project_name,

                goal=
                goal
            )

            save_location = (

                ProjectWriter()
                .save(

                    project_name=
                    project_name,

                    files=
                    project_files,

                    metadata={

                        "idea":
                        goal,

                        "project_type":
                        "api",

                        "entity":
                        project_name
                    }
                )
            )

            workspace_result = (

                self.workspace
                .add_project(

                    project_name=
                    project_name,

                    project_path=
                    f"generated/{project_name}"
                )
            )

            return {

                "success":
                True,

                "saved_to":
                save_location,

                "workspace":
                workspace_result,

                "validation":
                validation
            }

        return {

            "step":
            step,

            "status":
            "unknown"
        }