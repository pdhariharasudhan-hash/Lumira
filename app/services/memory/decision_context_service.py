class DecisionContextService:
    def __init__(self, memory_service=None):
        self.memory_service = memory_service

    def recent(self, limit=20):
        if self.memory_service is None:
            from app.services.memory.memory_service import MemoryService
            memory = MemoryService()
        else:
            memory = self.memory_service
        try:
            data = memory._read_cognitive_memory()
        except Exception:
            data = {}
        records = data.get('decisions', []) if isinstance(data, dict) else []
        return {'success': True, 'count': len(records[:limit]), 'records': records[:limit]}
