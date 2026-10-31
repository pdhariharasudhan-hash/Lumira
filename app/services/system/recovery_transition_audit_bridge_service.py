class RecoveryTransitionAuditBridgeService:
    """Record the result of a recovery transition through cognitive memory."""

    def __init__(self, audit_service):
        self.audit_service = audit_service

    def record(self, proposal, apply_result, project_id=None):
        return self.audit_service.record(
            proposal["workflow_id"],
            proposal["task_id"],
            proposal,
            apply_result,
            project_id,
        )
