class RecoveryTransitionProposalService:
    """Propose, but never silently apply, a post-recovery task transition."""

    def __init__(self, work_item_service, resume_service):
        self.work_item_service = work_item_service
        self.resume_service = resume_service

    def propose(self, workflow_id, task_id, task_plan, completed_steps, recommendation, project_id=None):
        workflow = self.work_item_service.get_workflow(workflow_id)
        if workflow is None:
            raise KeyError("workflow not found")
        task = next((item for item in workflow.get("tasks", []) if item.get("task_id") == task_id), None)
        if task is None:
            raise KeyError("task not found")

        resume = self.resume_service.evaluate(task_plan, completed_steps, recommendation, project_id)
        dependencies = set(task.get("dependencies", []))
        completed = {item.get("task_id") for item in workflow.get("tasks", []) if item.get("status") == "completed"}
        dependencies_ready = dependencies.issubset(completed)
        current_status = task.get("status")

        allowed = (
            resume.get("resume_allowed", False)
            and dependencies_ready
            and current_status in {"failed", "blocked", "pending"}
        )
        return {
            "success": True,
            "workflow_id": workflow_id,
            "task_id": task_id,
            "current_status": current_status,
            "proposed_status": "in_progress" if allowed else None,
            "transition_allowed": allowed,
            "dependencies_ready": dependencies_ready,
            "resume": resume,
            "reason": None if allowed else (
                "dependencies_incomplete" if not dependencies_ready else
                resume.get("recheck", {}).get("reason", "resume_not_allowed")
            ),
        }
