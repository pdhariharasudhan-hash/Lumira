class RecoveryPlanBridgeService:
    """Bridge task evidence into the existing recovery planning layer."""

    def __init__(self, package_service, task_plan_service):
        self.package_service = package_service
        self.task_plan_service = task_plan_service

    def build(self, workflow_id, task_id):
        package = self.package_service.build(workflow_id, task_id)
        task_plan = self.task_plan_service.plan(package)
        return {
            "success": True,
            "package": package,
            "task_plan": task_plan,
        }
