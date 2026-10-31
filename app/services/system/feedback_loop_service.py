class FeedbackLoopService:
    def __init__(self, event_service=None):
        self.event_service = event_service

    def record(self, action, outcome, project_id=None, goal_id=None):
        if self.event_service is None:
            from app.services.system.core_event_log_service import CoreEventLogService
            service = CoreEventLogService()
        else:
            service = self.event_service
        event = 'execution_success' if outcome == 'success' else 'execution_failure'
        return service.record(event, 'execution_feedback', {'action': action, 'outcome': outcome}, project_id=project_id, goal_id=goal_id)
