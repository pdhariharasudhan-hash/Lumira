from typing import Any

class PersonalBriefingService:
    def __init__(self, goal_attention=None, next_actions=None, notifications=None, context_service=None):
        self.goal_attention = goal_attention
        self.next_actions = next_actions
        self.notifications = notifications
        self.context_service = context_service

    def build(self, project_id: str | None = None) -> dict[str, Any]:
        goals = self.goal_attention.attention(project_id) if self.goal_attention else {"goals": []}
        actions = self.next_actions.ready(project_id) if self.next_actions else {"actions": []}
        inbox = self.notifications.list(unread_only=True) if self.notifications else {"notifications": []}
        context = self.context_service.recent(5) if self.context_service else {"records": []}
        return {"success": True, "attention": goals.get("goals", []), "next_actions": actions.get("actions", []), "notifications": inbox.get("notifications", []), "recent_context": context.get("records", [])}
