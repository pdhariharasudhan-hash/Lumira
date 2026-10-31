class ProgressSignalService:
    def __init__(self, action_service, blocker_service):
        self.action_service = action_service
        self.blocker_service = blocker_service

    def signal(self, project_id=None):
        actions = self.action_service.ready(project_id=project_id, limit=200)
        blockers = self.blocker_service.list(project_id=project_id, limit=200)
        ready = actions.get('count', len(actions.get('actions', [])))
        blocked = blockers.get('count', len(blockers.get('blockers', [])))
        signal = 'blocked' if blocked else ('moving' if ready else 'waiting')
        return {'success': True, 'signal': signal, 'ready_actions': ready, 'blockers': blocked}
