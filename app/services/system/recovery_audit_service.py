from datetime import datetime, timezone
from uuid import uuid4

class RecoveryAuditService:
    """Create immutable-shaped recovery records for later learning."""

    def __init__(self, memory_service):
        self.memory_service = memory_service

    def record(self, workflow_id, task_id, proposal, apply_result, project_id=None):
        record = {
            "recovery_id": str(uuid4()),
            "workflow_id": workflow_id,
            "task_id": task_id,
            "project_id": project_id,
            "transition_allowed": proposal.get("transition_allowed", False),
            "proposed_status": proposal.get("proposed_status"),
            "proposal_reason": proposal.get("reason"),
            "resume_allowed": proposal.get("resume", {}).get("resume_allowed", False),
            "recheck": proposal.get("resume", {}).get("recheck"),
            "applied": apply_result.get("applied", False),
            "apply_reason": apply_result.get("reason"),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self.memory_service.record_recovery(record)
        return {"success": True, "record": record}
