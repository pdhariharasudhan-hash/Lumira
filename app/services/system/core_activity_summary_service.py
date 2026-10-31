from collections import Counter

class CoreActivitySummaryService:
    def __init__(self, event_service=None):
        self.event_service = event_service

    def summary(self, limit=100):
        if self.event_service is None:
            from app.services.system.core_event_log_service import CoreEventLogService
            service = CoreEventLogService()
        else:
            service = self.event_service
        events = service.recent(limit).get('events', [])
        counts = Counter(str(item.get('source', 'unknown')) for item in events if isinstance(item, dict))
        return {'success': True, 'event_count': len(events), 'sources': dict(counts)}
