from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from app.services.system.core_event_log_service import CoreEventLogService
from app.services.system.event_insights_service import EventInsightsService

router=APIRouter(prefix="/core/events",tags=["core-events"])
_service=CoreEventLogService()

class CoreEvent(BaseModel):
    event:str=Field(min_length=1,max_length=200)
    source:str=Field(min_length=1,max_length=200)
    data:dict=Field(default_factory=dict)
    session_id:str|None=None
    project_id:str|None=None
    goal_id:str|None=None

@router.post("")
def record_event(request:CoreEvent):
    return _service.record(request.event,request.source,request.data,request.session_id,request.project_id,request.goal_id)

@router.get("")
def recent_events(limit:int=Query(50,ge=1,le=200)):
    return _service.recent(limit)


@router.get("/search")
def search_events(event: str | None = None, source: str | None = None, limit: int = Query(100, ge=1, le=500)):
    return _service.search(event, source, limit)


@router.get("/insights")
def event_insights(limit: int = Query(200, ge=1, le=500)):
    return _insights.summary(limit)
