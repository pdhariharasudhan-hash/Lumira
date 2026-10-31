class ExecutionReviewService:
    def __init__(self, readiness_service, outcome_service):
        self.readiness_service = readiness_service
        self.outcome_service = outcome_service

    def review(self, project_id=None):
        readiness = self.readiness_service.status(project_id)
        outcomes = self.outcome_service.summary()
        recommendation = 'resolve_blockers' if readiness.get('state') == 'blocked' else ('continue_execution' if readiness.get('state') == 'ready' else 'plan_next_step')
        if outcomes.get('failures', 0) > outcomes.get('successes', 0):
            recommendation = 'review_recent_failures'
        return {'success': True, 'execution_state': readiness.get('state'), 'recommendation': recommendation, 'outcomes': outcomes}
