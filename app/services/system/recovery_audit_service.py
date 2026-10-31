from datetime import datetime, timezone
from uuid import uuid4

class RecoveryAuditService:
    """Persist recovery attempts through Lumira's cognitive memory."""

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
            "applied": apply_result.get("applied", False),
            "apply_reason": apply_result.get("reason"),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        outcome = "resumed" if record["applied"] else "not_resumed"
        experience = self.memory_service.record_experience(
            "workflow",
            f"Recovery {record['recovery_id']} for workflow {workflow_id} task {task_id}",
            outcome,
            project_id=project_id,
            lessons=[record["apply_reason"] or record["proposal_reason"] or "recovery_attempt"],
        )
        return {"success": True, "record": record, "experience": experience}
