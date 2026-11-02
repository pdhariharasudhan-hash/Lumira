from app.core.service_registry import ServiceRegistry
from app.core.system_status import SystemStatus


class LumiraCore:
    MAX_GOAL_LENGTH = 10000

    def __init__(self):
        self.registry = ServiceRegistry()
        self.system_status = SystemStatus()

    def plan(self, goal: str):
        return self.registry.get("planner").create_plan(goal)

    def understand(self, request: str, session_id: str = "", project: str = "", metadata: dict | None = None):
        """Run a request through Lumira's full intelligence pipeline.

        This is the bridge between the legacy deterministic core and the
        modular Brain architecture. Existing build/run behavior remains
        unchanged while callers that need intent, goals, context, reasoning,
        planning and learning can use the same public core.
        """
        if not isinstance(request, str) or not request.strip() or len(request) > self.MAX_GOAL_LENGTH:
            return self._stopped(
                "validate",
                None,
                error={"code": "invalid_input", "message": "Request must contain 1 to 10000 characters."},
            )

        from app.services.brain.brain_request import BrainRequest
        from app.services.brain.brain_service import BrainService

        response = BrainService().execute(
            BrainRequest(
                message=request.strip(),
                session_id=session_id,
                project=project,
                metadata=dict(metadata or {}),
            )
        )
        state = response.state.model_dump(mode="json") if response.state is not None else None
        return {
            "success": bool(response.success),
            "status": "accept" if response.success else "reject",
            "current_stage": state.get("current_stage", "") if isinstance(state, dict) else "brain",
            "last_completed_stage": state.get("last_completed_stage") if isinstance(state, dict) else None,
            "final_status": state.get("status") if isinstance(state, dict) else ("completed" if response.success else "failed"),
            "state": state,
            "trace": response.trace or [],
            "error": response.error,
        }

    def build(self, goal: str):
        return self.registry.get("builder").build(goal)

    @staticmethod
    def _stopped(stage, last_completed, **details):
        return {
            "success": False,
            "status": details.pop("status", "refine"),
            "current_stage": stage,
            "last_completed_stage": last_completed,
            "final_status": "stopped",
            "retry_count": 0,
            **details,
        }

    def _execute_after_build(self, goal: str, builder: dict):
        if not isinstance(builder, dict) or builder.get("status") != "accept":
            return self._stopped("builder", None, builder=builder)
        execution = self.registry.get("execute").execute(goal, builder)
        if not isinstance(execution, dict) or execution.get("status") != "accept":
            status = execution.get("status", "refine") if isinstance(execution, dict) else "refine"
            return self._stopped("execute", "builder", status=status, builder=builder, execution=execution)
        return execution

    def execute(self, goal: str):
        if not isinstance(goal, str) or not goal.strip() or len(goal) > self.MAX_GOAL_LENGTH:
            return self._stopped("validate", None, error={"code": "invalid_input", "message": "Goal must contain 1 to 10000 characters."})
        builder = self.build(goal)
        execution = self._execute_after_build(goal, builder)
        if not isinstance(execution, dict) or execution.get("status") != "accept":
            return execution
        return execution

    def generate(self, goal: str):
        execution = self.execute(goal)
        if not isinstance(execution, dict) or execution.get("status") != "accept":
            return execution
        return self.registry.get("code").generate(goal, execution)

    def run(self, goal: str):
        if not isinstance(goal, str) or not goal.strip() or len(goal) > self.MAX_GOAL_LENGTH:
            return self._stopped("validate", None, error={"code": "invalid_input", "message": "Goal must contain 1 to 10000 characters."})

        builder = self.build(goal)
        if not isinstance(builder, dict) or builder.get("status") != "accept":
            return self._stopped("builder", None, builder=builder)

        execution = self.registry.get("execute").execute(goal, builder)
        if not isinstance(execution, dict) or execution.get("status") != "accept":
            status = execution.get("status", "refine") if isinstance(execution, dict) else "refine"
            return self._stopped("execute", "builder", status=status, builder=builder, execution=execution)

        code = self.registry.get("code").generate(goal, execution)
        validation = self._validate_code(code)
        if not isinstance(code, dict) or code.get("status", "accept") != "accept" or not validation["valid"]:
            return {
                "success": False,
                "status": "reject",
                "current_stage": "verify_code",
                "last_completed_stage": "execute",
                "final_status": "failed",
                "retry_count": 0,
                "goal": goal,
                "builder": builder,
                "execution": execution,
                "code": code,
                "validation": validation,
            }

        project_name = code.get("code_target")
        files = code.get("files")
        if not isinstance(project_name, str) or not isinstance(files, dict) or not files:
            return {
                "success": False,
                "status": "reject",
                "current_stage": "save",
                "last_completed_stage": "code",
                "final_status": "failed",
                "retry_count": 0,
                "goal": goal,
                "builder": builder,
                "execution": execution,
                "code": code,
                "validation": validation,
                "error": {"code": "invalid_project", "message": "Generated project name and files are required."},
            }

        from app.services.projects.project_writer import ProjectWriter

        try:
            saved_to = ProjectWriter().save(
                project_name,
                files,
                {"idea": goal, "project_type": "api", "entity": project_name, "project": project_name},
            )
        except (OSError, ValueError) as error:
            return {
                "success": False,
                "status": "reject",
                "current_stage": "save",
                "last_completed_stage": "code",
                "final_status": "failed",
                "retry_count": 0,
                "goal": goal,
                "builder": builder,
                "execution": execution,
                "code": code,
                "validation": validation,
                "error": {"code": "save_failed", "message": str(error)},
            }

        return {
            "success": True,
            "status": "accept",
            "current_stage": "complete",
            "last_completed_stage": "save",
            "final_status": "completed",
            "retry_count": 0,
            "goal": goal,
            "builder": builder,
            "execution": execution,
            "code": code,
            "validation": validation,
            "saved_to": saved_to,
        }

    @staticmethod
    def _validate_code(code):
        from app.services.validation.code_validation_service import CodeValidationService

        files = code.get("files", {}) if isinstance(code, dict) else {}
        return CodeValidationService().validate(files)

    def status(self):
        return self.system_status.get_status()
