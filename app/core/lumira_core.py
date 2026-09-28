from app.core.service_registry import ServiceRegistry
from app.core.system_status import SystemStatus


class LumiraCore:
    MAX_GOAL_LENGTH = 10000

    def __init__(self):
        self.registry = ServiceRegistry()
        self.system_status = SystemStatus()

    def plan(self, goal: str):
        return self.registry.get("planner").create_plan(goal)

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
