class ActionPriorityService:
    def rank(self, actions, attention=None):
        attention = attention or []
        urgent_goals = {item.get('goal_id') for item in attention if isinstance(item, dict)}
        ranked = []
        for action in actions or []:
            if not isinstance(action, dict):
                continue
            item = dict(action)
            item['priority_score'] = 100 if item.get('goal_id') in urgent_goals else 50
            ranked.append(item)
        ranked.sort(key=lambda item: item['priority_score'], reverse=True)
        return {'success': True, 'count': len(ranked), 'actions': ranked}
