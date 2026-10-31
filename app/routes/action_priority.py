from fastapi import APIRouter
from app.services.work_items.action_priority_service import ActionPriorityService
from app.services.work_items.next_action_service import NextActionService
from app.services.goals.goal_attention_service import GoalAttentionService

router = APIRouter(prefix='/workflows', tags=['workflows'])
_ranker = ActionPriorityService()
_actions = NextActionService()
_attention = GoalAttentionService()

@router.get('/prioritized-actions')
def prioritized_actions():
    ready = _actions.ready().get('actions', [])
    attention = _attention.attention().get('goals', [])
    return _ranker.rank(ready, attention)
