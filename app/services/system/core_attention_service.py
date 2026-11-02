class CoreAttentionService:
    def __init__(self, briefing_service, priority_service):
        self.briefing_service = briefing_service
        self.priority_service = priority_service

    def snapshot(self, limit=5):
        briefing = self.briefing_service.build()
        ranked = self.priority_service.prioritize(briefing)
        return {"success": True, "attention_count": ranked["count"], "top_attention": ranked["items"][:limit]}
