from app.services.memory.memory_service import MemoryService
from app.services.system.core_event_log_service import CoreEventLogService


class FeedbackLoopService:
    """Persist execution feedback to both the event timeline and cognitive memory."""

    def __init__(self, event_service=None, memory_service=None):
        self.event_service = event_service or CoreEventLogService()
        self.memory_service = memory_service or MemoryService()

    def record(self, action, outcome, project_id=None, goal_id=None):
        event = "execution_success" if outcome == "success" else "execution_failure"
        event_result = self.event_service.record(
            event, "execution_feedback",
            {"action": action, "outcome": outcome},
            project_id=project_id, goal_id=goal_id,
        )
        memory_result = self.memory_service.record_experience(
            experience_type=outcome,
            summary=f"Execution outcome: {action}",
            outcome=outcome,
            project_id=project_id,
            goal_id=goal_id,
            verified=True,
        )
        return {
            "success": bool(event_result.get("success")) and bool(memory_result.get("success")),
            "event": event_result,
            "memory": memory_result,
        }
