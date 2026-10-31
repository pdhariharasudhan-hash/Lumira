class RecoveryGuidanceService:
    def __init__(self, context_service, plan_service):
        self.context_service = context_service
        self.plan_service = plan_service

    def guidance(self, project_id=None):
        context = self.context_service.build(project_id)
        plan = self.plan_service.plan(context)
        return {"success": True, "recovery_required": context["recovery_required"], "context": context, "plan": plan}
