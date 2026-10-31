class BriefingPriorityService:
    def prioritize(self, briefing):
        items = []
        for item in briefing.get("attention", []):
            if isinstance(item, dict):
                items.append({"kind": "goal_attention", "priority": 100, "data": item})
        for item in briefing.get("notifications", []):
            if isinstance(item, dict) and item.get("level") in {"warning", "error"}:
                priority = 90 if item.get("level") == "error" else 80
                items.append({"kind": "notification", "priority": priority, "data": item})
        for item in briefing.get("next_actions", []):
            if isinstance(item, dict):
                items.append({"kind": "next_action", "priority": 50, "data": item})
        items.sort(key=lambda value: value["priority"], reverse=True)
        return {"success": True, "count": len(items), "items": items}
