class DecisionSnapshotService:
    def __init__(self, readiness_service, attention_service):
        self.readiness_service = readiness_service
        self.attention_service = attention_service

    def snapshot(self, project_id=None):
        readiness = self.readiness_service.status(project_id)
        attention = self.attention_service.snapshot()
        state = readiness.get('state', 'idle')
        recommendation = 'resolve_blockers' if state == 'blocked' else ('execute_next_action' if state == 'ready' else 'review_goals')
        return {'success': True, 'state': state, 'recommendation': recommendation, 'ready_actions': readiness.get('ready_action_count', 0), 'blockers': readiness.get('blocker_count', 0), 'attention': attention.get('top_attention', [])[:3]}
