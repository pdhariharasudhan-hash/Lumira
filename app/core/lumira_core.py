from app.core.service_registry import ServiceRegistry
from app.core.system_status import SystemStatus


class LumiraCore:
    MAX_GOAL_LENGTH = 10000

    def __init__(self):
        self.registry = ServiceRegistry()
        self.system_status = SystemStatus(registry=self.registry)

    def plan(self, goal: str):
        return self.registry.get("planner").create_plan(goal)

    def core_context(self, session_id: str = "", project_id: str = "", goal_id: str = ""):
        from app.services.system.core_runtime_bridge_service import CoreRuntimeBridgeService
        return CoreRuntimeBridgeService().context(
            session_id or None,
            project_id or None,
            goal_id or None,
        )

    def understand(
        self,
        request: str,
        session_id: str = "",
        project: str = "",
        metadata: dict | None = None,
        workspace: str = "default",
    ):
        """Run a request through Lumira's modular intelligence pipeline."""
        if not isinstance(request, str) or not request.strip() or len(request) > self.MAX_GOAL_LENGTH:
            return self._stopped(
                "validate",
                None,
                error={
                    "code": "invalid_input",
                    "message": "Request must contain 1 to 10000 characters.",
                },
            )

        from app.services.brain.brain_request import BrainRequest
        from app.services.brain.brain_service import BrainService

        request_metadata = dict(metadata or {})
        request_metadata.setdefault(
            "core_context",
            self.core_context(session_id=session_id, project_id=project).get("context", {}),
        )
        response = BrainService().execute(
            BrainRequest(
                message=request.strip(),
                session_id=session_id,
                project=project,
                workspace=workspace,
                metadata=request_metadata,
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
        from app.services.brain.brain_request import BrainRequest
        from app.services.brain.brain_service import BrainService

        response = BrainService().execute(
            BrainRequest(
                message=goal.strip(),
                metadata={
                    "execute_capability": "project_generation",
                    "capability_payload": {"idea": goal.strip()},
                },
            )
        )
        state = getattr(response, "state", None)
        result = getattr(state, "execution_result", None)
        result = result if isinstance(result, dict) else {}
        builder = result.get("builder")
        execution = result.get("execution")
        code = result.get("code")
        validation = result.get("validation")
        saved_to = result.get("saved_path")
        builder = builder if isinstance(builder, dict) else None
        execution = execution if isinstance(execution, dict) else None
        code = code if isinstance(code, dict) else None
        validation = validation if isinstance(validation, dict) else None

        validation_ok = validation is not None and validation.get(
            "valid", validation.get("success", False)
        ) is True
        generation_complete = (
            getattr(response, "success", False) is True
            and result.get("success") is True
            and builder is not None
            and builder.get("status") == "accept"
            and execution is not None
            and execution.get("status") == "accept"
            and code is not None
            and code.get("status", "accept") == "accept"
            and validation_ok
            and isinstance(saved_to, str)
            and bool(saved_to)
        )
        if not generation_complete:
            if builder and builder.get("status") != "accept":
                stage, last_completed = "builder", None
            elif execution and execution.get("status") != "accept":
                stage, last_completed = "execute", "builder"
            elif code is not None and (not validation_ok or code.get("status", "accept") != "accept"):
                stage, last_completed = "verify_code", "execute"
            elif builder is None and execution is None and code is None:
                stage, last_completed = "brain", None
            elif execution is None:
                stage, last_completed = "execute", "builder"
            elif code is None:
                stage, last_completed = "verify_code", "execute"
            elif not isinstance(saved_to, str) or not saved_to:
                stage, last_completed = "save", "code" if code is not None else None
            else:
                stage, last_completed = "brain", None
            error = result.get("error") or getattr(response, "error", None)
            failure = {
                "success": False,
                "status": "reject",
                "current_stage": stage,
                "last_completed_stage": last_completed,
                "final_status": "failed",
                "retry_count": 0,
                "goal": goal,
                "builder": builder,
                "execution": execution,
                "code": code,
                "validation": validation,
            }
            if error is not None:
                failure["error"] = error
            return failure

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
