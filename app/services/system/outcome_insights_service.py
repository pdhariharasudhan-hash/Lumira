class OutcomeInsightsService:
    def __init__(self, event_service=None):
        self.event_service = event_service

    def summary(self, limit=100):
        if self.event_service is None:
            from app.services.system.core_event_log_service import CoreEventLogService
            service = CoreEventLogService()
        else:
            service = self.event_service
        events = service.recent(limit).get('events', [])
        successes = sum(1 for item in events if isinstance(item, dict) and item.get('event') == 'execution_success')
        failures = sum(1 for item in events if isinstance(item, dict) and item.get('event') == 'execution_failure')
        total = successes + failures
        return {'success': True, 'outcomes': total, 'successes': successes, 'failures': failures, 'success_rate': round(successes / total, 3) if total else None}
