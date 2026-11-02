from app.services.command_parser_service import CommandParserService


class IntentClassifierService:
    """Classify common intent labels using deterministic parser output when available."""

    def classify(self, command: str) -> str:
        if not isinstance(command, str) or not command.strip():
            return "chat"

        text = command.strip().lower()

        # Preserve the existing high-confidence labels for compatibility.
        if "enter " in text and " mode" in text:
            return "mode"
        if text.startswith("build"):
            return "build"
        if text.startswith("add "):
            return "continue"
        if text.startswith("search"):
            return "search"
        if text.startswith("continue"):
            return "continue"
        if text.startswith("show"):
            return "show"

        parsed = CommandParserService().parse(command)
        if not parsed.get("success"):
            return "chat"

        capability = parsed.get("capability")
        if capability == "agent_task":
            agent_name = parsed.get("payload", {}).get("agent_name")
            return {
                "code_agent": "build",
                "planner_agent": "plan",
                "research_agent": "research",
            }.get(agent_name, "agent")

        categories = {
            "activate_mode": "mode",
            "search": "search",
            "list_features": "show",
            "resume_project": "continue",
            "continue_project": "continue",
            "project_generation": "build",
            "project_engineering": "build",
            "project_versioning": "build",
            "debugging": "build",
            "technical_research": "research",
            "knowledge_retrieval": "research",
            "research": "research",
            "comparison": "research",
            "web_access": "research",
            "business_plan": "plan",
            "planning": "plan",
            "goals": "plan",
            "tasks": "plan",
            "growth_strategy": "plan",
            "product_improvement": "plan",
            "user_growth": "plan",
            "optimization": "plan",
            "market_analysis": "research",
            "revenue_analysis": "research",
            "competitive_analysis": "research",
            "business_operations": "operations",
            "workflow_automation": "operations",
            "scheduled_tasks": "operations",
            "monitoring": "operations",
            "activate_feature": "control",
            "deactivate_feature": "control",
            "generate_image": "create",
            "video_generation": "create",
            "document_generation": "create",
            "presentations": "create",
            "posters": "create",
            "thumbnails": "create",
            "scripts": "create",
            "marketing_assets": "create",
            "content_planning": "create",
            "diagram_generation": "create",
            "architecture_diagrams": "create",
            "flowcharts": "create",
            "blueprint_generation": "create",
            "schematic_generation": "create",
            "ui_design": "create",
            "personal_context": "personal",
            "notes": "personal",
            "reminders": "personal",
            "scheduling": "personal",
            "daily_planning": "plan",
            "notifications": "personal",
            "personal_organization": "personal",
            "email": "personal",
            "voice": "personal",
            "project_pipeline": "build",
        }
        return categories.get(capability, "chat")
