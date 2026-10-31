class TaskRecoveryEvidenceService:
    """Extract bounded failure evidence from a concrete workflow task."""

    def __init__(self, work_item_service):
        self.work_item_service = work_item_service

    def evidence(self, workflow_id, task_id):
        workflow = self.work_item_service.get_workflow(workflow_id)
        task = next((item for item in workflow.get("tasks", []) if item.get("task_id") == task_id), None)
        if task is None:
            raise KeyError(task_id)
        return {
            "success": True,
            "workflow_id": workflow_id,
            "task_id": task_id,
            "status": task.get("status"),
            "blocker": task.get("blocker"),
            "result": task.get("result"),
            "updated_at": task.get("updated_at"),
        }
