from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.notifications.notification_service import NotificationService
from app.services.notifications.notification_insights_service import NotificationInsightsService

router = APIRouter(prefix="/notifications", tags=["notifications"])
_service = NotificationService()
_insights = NotificationInsightsService(_service)


class NotificationCreateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    level: str = "info"
    session_id: str | None = None
    project_id: str | None = None
    goal_id: str | None = None


@router.post("")
def create_notification(request: NotificationCreateRequest):
    return _service.create(
        request.message, request.level, request.session_id,
        request.project_id, request.goal_id,
    )


@router.get("")
def list_notifications(unread_only: bool = False):
    return _service.list(unread_only)


@router.post("/{notification_id}/read")
def mark_notification_read(notification_id: str):
    return _service.mark_read(notification_id)


@router.post("/read-all")
def mark_all_notifications_read():
    return _service.mark_all_read()


@router.delete("/{notification_id}")
def delete_notification(notification_id: str):
    return _service.delete(notification_id)


@router.get("/insights")
def notification_insights():
    return _insights.summary()
