from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.reminders.reminder_service import ReminderService

router = APIRouter(prefix="/reminders", tags=["reminders"])
_service = ReminderService()


class ReminderCreateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    due_at: str
    session_id: str | None = None
    project_id: str | None = None
    goal_id: str | None = None


@router.post("")
def create_reminder(request: ReminderCreateRequest):
    return _service.create(
        request.message, request.due_at, request.session_id,
        request.project_id, request.goal_id,
    )


@router.get("")
def list_reminders():
    return _service.list()


@router.get("/due")
def due_reminders():
    return _service.due()
