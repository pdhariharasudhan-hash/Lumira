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
from app.services.sessions.session_manager_service import redact_sensitive_value


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
            from app.routes.validate import analyze_idea

            validation = analyze_idea(goal)
            if validation["verdict"] == "reject":
                return {"success": False, "state": "stopped", "step": step, "validation": validation}
            return {"success": True, "state": "completed", "step": step, "validation": validation}

        if step == "builder":

            return (
                self.core.build(
                    goal
                )
            )

        if step == "execute":
            executor = self.core.registry.get("execute")
            return executor.execute(goal, context.get("builder"))

        if step == "code":
            from app.services.code.code_service import CodeService

            generated = CodeService().generate(goal, context.get("execute", {}))
            validation = self.validator.validate(generated.get("files", {}))
            if not validation["valid"]:
                return {"success": False, "state": "failed", "step": step, "code": "generated_code_invalid", "validation": validation}
            generated["success"] = True
            generated["validation"] = validation
            return generated

        if step == "search":
            from app.services.search.unified_search_service import UnifiedSearchService

            return {"success": True, "state": "completed", "results": UnifiedSearchService().search_all(goal)}

        if step == "generate_image":
            from app.services.image.image_generation_service import ImageGenerationService

            return ImageGenerationService().generate(goal)

        if step == "save_artifact":
            import json
            from app.services.artifacts.artifact_manager_service import ArtifactManagerService

            safe_payload = redact_sensitive_value({
                "goal": goal,
                "completed_stages": context,
            })
            content = json.dumps(safe_payload, ensure_ascii=False, indent=2, default=str)
            if len(content) > ArtifactManagerService.MAX_CONTENT_LENGTH:
                return {
                    "success": False,
                    "code": "artifact_content_too_large",
                    "message": "Workflow results exceed the artifact storage limit.",
                }
            try:
                artifact = ArtifactManagerService().create_artifact(
                    artifact_type="reports",
                    content=content,
                    source="workflow_engine",
                    extension="json",
                )
            except Exception:
                return {
                    "success": False,
                    "code": "artifact_storage_failed",
                    "message": "Workflow results could not be saved as an artifact.",
                }
            return {"success": True, "state": "completed", "step": step, "artifact": artifact}

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

        return {"success": False, "state": "rejected", "step": step, "code": "unsupported_workflow_step", "message": f"Workflow step '{step}' is not implemented."}
