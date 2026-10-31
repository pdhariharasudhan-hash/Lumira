class WorkflowRecoveryContextService:
    """Attach project recovery guidance to a concrete persisted workflow."""

    def __init__(self, work_item_service, recovery_guidance_service):
        self.work_item_service = work_item_service
        self.recovery_guidance_service = recovery_guidance_service

    def build(self, workflow_id, project_id=None):
        workflow = self.work_item_service.get_workflow(workflow_id)
        guidance = self.recovery_guidance_service.guidance(project_id)
        tasks = workflow.get("tasks", [])
        affected = [
            {"task_id": task.get("task_id"), "title": task.get("title"), "status": task.get("status")}
            for task in tasks
            if task.get("status") in {"failed", "blocked", "in_progress"}
        ]
        return {
            "success": True,
            "workflow_id": workflow_id,
            "workflow_status": workflow.get("status"),
            "affected_tasks": affected,
            "recovery": guidance,
        }
