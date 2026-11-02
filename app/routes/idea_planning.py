from fastapi import APIRouter, HTTPException
from app.services.ideas.idea_planning_service import IdeaPlanningService

router = APIRouter(prefix="/ideas", tags=["Idea Planning"])
service = IdeaPlanningService()

@router.post("/{idea_id}/plan")
def plan_idea(idea_id: str):
    try:
        return {"success": True, "plan": service.create_plan(idea_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
