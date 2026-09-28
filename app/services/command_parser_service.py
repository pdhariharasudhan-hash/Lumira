from typing import Any, Dict


class CommandParserService:
    """
    Deterministic natural-language command parser.

    Converts recognized user commands into capability
    requests without executing anything.
    """

    def parse(self, command: str) -> Dict[str, Any]:
        if not isinstance(command, str):
            return {
                "success": False,
                "message": "Command must be a string",
            }

        text = command.strip().lower()

        if not text:
            return {
                "success": False,
                "message": "Command cannot be empty",
            }

        if any(phrase in text for phrase in (
            "business plan", "plan for launching", "plan to launch",
            "launch my business", "launch my ", "launching my", "business idea",
        )):
            return {
                "success": True,
                "capability": "business_plan",
                "payload": {"request": command},
            }

        if text.startswith(("generate", "create", "make")) and any(term in text for term in ("video", "clip", "animation")):
            return {"success": True, "capability": "video_generation", "payload": {"request": command}}

        if text.startswith(("generate", "create", "write", "draft")) and any(term in text for term in ("report", "document", "pdf")):
            return {"success": True, "capability": "document_generation", "payload": {"request": command}}

        if "today" in text and any(term in text for term in ("tasks", "work", "operations")):
            return {
                "success": True,
                "capability": "business_operations",
                "payload": {"command": command},
            }

        if text.startswith(("generate", "create", "design", "make")) and any(
            term in text for term in ("diagram", "flowchart", "blueprint", "schematic", "architecture diagram", "ui design", "dashboard")
        ):
            capability = (
                "blueprint_generation" if "blueprint" in text else
                "architecture_diagrams" if "architecture" in text else
                "flowcharts" if "flowchart" in text else
                "schematic_generation" if "schematic" in text else
                "diagram_generation" if "diagram" in text else
                "ui_design"
            )
            return {"success": True, "capability": capability, "payload": {"request": command}}

        if "enter " in text and " mode" in text:
            requested_mode = text.split("enter ", 1)[1].split(" mode", 1)[0]
            requested_mode = requested_mode.strip(" .!?").replace(" ", "_")
            supported_modes = {
                "personal", "builder", "growth", "creator",
                "generator", "research", "assistant", "operations", "business",
            }
            if requested_mode in supported_modes:
                return {
                    "success": True,
                    "capability": "activate_mode",
                    "payload": {"mode": requested_mode},
                }

        # ----------------------------------------------------
        # IMAGE GENERATION
        # ----------------------------------------------------

        if (
            "generate image" in text
            or "generate an image" in text
        ):
            return {
                "success": True,
                "capability": "generate_image",
                "payload": {
                    "prompt": command,
                    "image_type": "image",
                },
            }

        # ----------------------------------------------------
        # SEARCH
        # ----------------------------------------------------

        if text.startswith("search "):
            return {
                "success": True,
                "capability": "search",
                "payload": {
                    "query": command[7:].strip(),
                },
            }

        # ----------------------------------------------------
        # FEATURE CONTROL
        # ----------------------------------------------------

        if text.startswith("activate "):
            return {
                "success": True,
                "capability": "activate_feature",
                "payload": {
                    "feature": command[9:].strip(),
                },
            }

        if text.startswith("disable "):
            return {
                "success": True,
                "capability": "deactivate_feature",
                "payload": {
                    "feature": command[8:].strip(),
                },
            }

        if text == "list features":
            return {
                "success": True,
                "capability": "list_features",
                "payload": {},
            }

        # ----------------------------------------------------
        # BUILDER
        # ----------------------------------------------------

        if (
            text.startswith(("build ", "create ", "make ", "generate "))
            and any(term in text for term in ("api", "application", "app", "backend", "project"))
        ):
            return {
                "success": True,
                "capability": "project_generation",
                "payload": {
                    "idea": command,
                },
            }

        if text.startswith("add "):
            return {
                "success": True,
                "capability": "continue_project",
                "payload": {"instruction": command},
            }

        if text.startswith(("make it ", "change it ", "update it ")):
            return {
                "success": True,
                "capability": "continue_project",
                "payload": {"instruction": command},
            }

        if text.startswith("continue "):
            return {
                "success": True,
                "capability": "resume_project",
                "payload": {},
            }

        builder_rules = [
            ("generate project", "project_generation"),
            ("create project", "project_generation"),
            ("version project", "project_versioning"),
            ("debug", "debugging"),
            ("develop", "project_engineering"),
        ]

        for phrase, capability in builder_rules:
            if phrase in text:
                return {
                    "success": True,
                    "capability": capability,
                    "payload": {
                        "idea": command,
                    },
                }

        # ----------------------------------------------------
        # OPERATIONS
        # ----------------------------------------------------

        operations_rules = [
            ("automate", "workflow_automation"),
            ("schedule", "scheduled_tasks"),
            ("monitor", "monitoring"),
            ("execute", "workflow_automation"),
            ("run", "workflow_automation"),
        ]

        for phrase, capability in operations_rules:
            if phrase in text:
                return {
                    "success": True,
                    "capability": capability,
                    "payload": {
                        "command": command,
                    },
                }

        # ----------------------------------------------------
        # RESEARCH
        # ----------------------------------------------------

        research_rules = [
            ("find information", "knowledge_retrieval"),
            ("investigate", "knowledge_retrieval"),
            ("compare", "comparison"),
            ("research", "technical_research"),
        ]

        for phrase, capability in research_rules:
            if phrase in text:
                return {
                    "success": True,
                    "capability": capability,
                    "payload": {
                        "query": command,
                    },
                }

        # ----------------------------------------------------
        # CREATOR
        # ----------------------------------------------------

        creator_rules = [
            ("create a presentation", "presentations"),
            ("create presentation", "presentations"),
            ("create a poster", "posters"),
            ("create poster", "posters"),
            ("create a thumbnail", "thumbnails"),
            ("create thumbnail", "thumbnails"),
            ("write a script", "scripts"),
            ("write script", "scripts"),
            ("create a post", "marketing_assets"),
            ("create post", "marketing_assets"),
            ("write a blog", "content_planning"),
            ("write", "content_planning"),
        ]

        for phrase, capability in creator_rules:
            if phrase in text:
                return {
                    "success": True,
                    "capability": capability,
                    "payload": {
                        "content": command,
                    },
                }

        # ----------------------------------------------------
        # GROWTH
        # ----------------------------------------------------

        growth_rules = [
            ("create business plan", "growth_strategy"),
            ("create a marketing strategy", "growth_strategy"),
            ("create marketing strategy", "growth_strategy"),
            ("analyze market", "market_analysis"),
            ("analyze revenue", "revenue_analysis"),
            ("improve product", "product_improvement"),
            ("grow users", "user_growth"),
            ("analyze competition", "competitive_analysis"),
            ("optimize", "optimization"),
        ]

        for phrase, capability in growth_rules:
            if phrase in text:
                return {
                    "success": True,
                    "capability": capability,
                    "payload": {
                        "request": command,
                    },
                }

        # ----------------------------------------------------
        # PERSONAL
        # ----------------------------------------------------

        personal_rules = [
            ("remember", "personal_context"),
            ("set goal", "goals"),
            ("create task", "tasks"),
            ("create a business plan", "planning"),
            ("create business plan", "planning"),
            ("plan", "planning"),
            ("remind", "reminders"),
            ("take note", "notes"),
        ]

        for phrase, capability in personal_rules:
            if phrase in text:
                return {
                    "success": True,
                    "capability": capability,
                    "payload": {
                        "request": command,
                    },
                }

        return {
            "success": False,
            "message": "Unknown command",
        }

