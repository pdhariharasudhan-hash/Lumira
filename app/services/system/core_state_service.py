class CoreStateService:
    def __init__(self, readiness_service, attention_service):
        self.readiness_service = readiness_service
        self.attention_service = attention_service

    def state(self, project_id=None):
        readiness = self.readiness_service.status(project_id)
        attention = self.attention_service.snapshot()
        execution_state = readiness.get('state', 'idle')
        core_state = 'attention_required' if execution_state == 'blocked' else ('active' if execution_state == 'ready' else 'idle')
        return {'success': True, 'state': core_state, 'execution': readiness, 'attention_count': attention.get('attention_count', 0)}
