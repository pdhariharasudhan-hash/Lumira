class OutcomePatternService:
    """Derive simple deterministic patterns from recent cognitive experiences."""

    def __init__(self, memory_service=None):
        self.memory_service = memory_service

    def summary(self, project_id=None, limit=100):
        if self.memory_service is None:
            from app.services.memory.memory_service import MemoryService
            memory = MemoryService()
        else:
            memory = self.memory_service
        data = memory._read_cognitive_memory()
        experiences = data.get("experiences", []) if isinstance(data, dict) else []
        if project_id:
            experiences = [item for item in experiences if isinstance(item, dict) and item.get("project_id") == project_id]
        experiences = experiences[-limit:]
        success = sum(1 for item in experiences if isinstance(item, dict) and item.get("outcome") == "success")
        failure = sum(1 for item in experiences if isinstance(item, dict) and item.get("outcome") == "failure")
        pattern = "failure_trend" if failure > success else ("success_trend" if success else "insufficient_data")
        return {"success": True, "pattern": pattern, "samples": len(experiences), "successes": success, "failures": failure}
