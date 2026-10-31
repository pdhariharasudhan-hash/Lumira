class CheckpointResumeAdapterService:
    """Invoke the existing WorkflowEngine resume only after checkpoint gating."""

    def __init__(self, orchestrator, workflow_engine):
        self.orchestrator = orchestrator
        self.workflow_engine = workflow_engine

    def resume(self, session_id, run, request_id, previous_request_ids=None):
        prepared = self.orchestrator.prepare(
            session_id, run, request_id, previous_request_ids
        )
        if not prepared.get("gate", {}).get("execute_resume"):
            return {
                "success": False,
                "state": "blocked",
                "run_id": run.get("run_id"),
                "code": "checkpoint_resume_blocked",
                "prepared": prepared,
            }
        result = self.workflow_engine.resume(run["run_id"])
        return {
            "success": result.get("success", False),
            "state": result.get("state"),
            "run_id": run.get("run_id"),
            "prepared": prepared,
            "result": result,
        }
