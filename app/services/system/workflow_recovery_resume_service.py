class WorkflowRecoveryResumeService:
    """Provide controlled resume guidance without mutating workflow state."""

    def __init__(self, completion_service, recheck_service):
        self.completion_service = completion_service
        self.recheck_service = recheck_service

    def evaluate(self, task_plan, completed_steps, recommendation, project_id=None):
        completion = self.completion_service.evaluate(completed_steps, task_plan)
        recheck = self.recheck_service.recheck(recommendation, completion, project_id)
        return {
            "success": True,
            "resume_allowed": bool(recheck.get("execution_allowed")),
            "completion": completion,
            "recheck": recheck,
        }
