from fastapi import APIRouter, Query

from app.services.work_items.action_priority_service import ActionPriorityService
from app.services.work_items.next_action_service import NextActionService
from app.services.work_items.blocker_queue_service import BlockerQueueService
from app.services.goals.goal_attention_service import GoalAttentionService

router = APIRouter(prefix="/workflows", tags=["workflows"])
_ranker = ActionPriorityService()
_actions = NextActionService()
_attention = GoalAttentionService()


@router.get("/prioritized-actions")
def prioritized_actions(
    project_id: str | None = Query(default=None, max_length=128),
    goal_id: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=50, ge=1, le=200),
):
    ready = _actions.ready(project_id=project_id, goal_id=goal_id, limit=200).get("actions", [])
    attention = _attention.attention(project_id=project_id).get("goals", [])
    blockers = BlockerQueueService().list(project_id=project_id, limit=200).get("blockers", [])
    ranked = _ranker.rank(ready, attention, blockers, limit=limit)
    ranked["project_id"] = project_id
    ranked["goal_id"] = goal_id
    return ranked
