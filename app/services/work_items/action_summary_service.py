class ActionSummaryService:
    def __init__(self, action_service):
        self.action_service = action_service

    def summary(self, project_id=None, limit=5):
        result = self.action_service.ready(project_id=project_id, limit=limit)
        actions = result.get('actions', [])
        return {'success': True, 'count': len(actions), 'message': 'No actions ready' if not actions else f'{len(actions)} action(s) ready', 'actions': actions}
