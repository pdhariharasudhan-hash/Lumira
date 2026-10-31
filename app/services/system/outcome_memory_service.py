class OutcomeMemoryService:
    """Persist execution outcomes into Lumira's existing cognitive memory."""

    def __init__(self, memory_service=None):
        self.memory_service = memory_service

    def record(self, action, outcome, project_id=None, goal_id=None):
        if self.memory_service is None:
            from app.services.memory.memory_service import MemoryService
            memory = MemoryService()
        else:
            memory = self.memory_service
        return memory.record_experience(
            outcome=outcome,
            description=f"Execution outcome: {action}",
            project_id=project_id,
            goal_id=goal_id,
        )
