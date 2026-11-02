class WorkflowRecoveryGuidanceService:
    def __init__(self, context_service, target_service):
        self.context_service = context_service
        self.target_service = target_service

    def guidance(self, workflow_id, project_id=None):
        context = self.context_service.build(workflow_id, project_id)
        target = self.target_service.select(context)
        return {
            "success": True,
            "workflow_id": workflow_id,
            "recovery_required": context["recovery"].get("recovery_required", False),
            "target": target,
            "context": context,
        }
