class RecoveryTransitionApplyService:
    """Apply only an already validated recovery transition proposal."""

    def __init__(self, work_item_service):
        self.work_item_service = work_item_service

    def apply(self, proposal, confirmation=False):
        if confirmation is not True:
            return {"success": False, "applied": False, "reason": "explicit_confirmation_required"}
        if not proposal.get("transition_allowed"):
            return {"success": False, "applied": False, "reason": proposal.get("reason", "transition_not_allowed")}
        updated = self.work_item_service.update_task(
            proposal["workflow_id"], proposal["task_id"], proposal["proposed_status"]
        )
        return {"success": True, "applied": True, "workflow": updated}
