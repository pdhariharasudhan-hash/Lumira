class ExecutionLoopService:
    def __init__(self, action_service, attention_service):
        self.action_service = action_service
        self.attention_service = attention_service

    def status(self):
        actions = self.action_service.ready()
        attention = self.attention_service.snapshot()
        return {
            "success": True,
            "ready_action_count": actions.get("count", len(actions.get("actions", []))),
            "attention_count": attention.get("attention_count", 0),
            "next_actions": actions.get("actions", [])[:5],
            "attention": attention.get("top_attention", []),
        }
