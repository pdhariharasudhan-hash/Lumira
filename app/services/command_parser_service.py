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

        # Agent delegation is explicit; ordinary commands never auto-dispatch.
        named_agent_prefixes = (
            ("delegate to code_agent: ", "code_agent"),
            ("delegate to planner_agent: ", "planner_agent"),
            ("delegate to research_agent: ", "research_agent"),
        )
        for prefix, agent_name in named_agent_prefixes:
            if text.startswith(prefix):
                task = command.strip()[len(prefix):].strip()
                if task:
                    return {
                        "success": True,
                        "capability": "agent_task",
                        "payload": {"task": task, "agent_name": agent_name},
                    }
                return {"success": False, "message": "Agent task cannot be empty"}

        agent_prefix = "delegate to agent: "
        if text.startswith(agent_prefix):
            task = command.strip()[len(agent_prefix):].strip()
            if task:
                return {
                    "success": True,
                    "capability": "agent_task",
                    "payload": {"task": task, "agent_name": None},
                }
            return {"success": False, "message": "Agent task cannot be empty"}

        # Deterministic Tamil and Tamil-English command forms. This is a
        # deliberately bounded phrase map, not a claim of general translation.
        search_prefixes = (
            "search pannu ", "search pannunga ", "thedu ", "thedunga ",
            "தேடு ", "தேடுங்கள் ",
        )
        for prefix in search_prefixes:
            if text.startswith(prefix):
                query = command.strip()[len(prefix):].strip()
                if query:
                    return {
                        "success": True,
                        "capability": "search",
                        "payload": {"query": query},
                    }
                return {"success": False, "message": "Search query cannot be empty"}

        if text in {
            "தொடரு", "தொடர்ந்து செய்", "மீண்டும் தொடரு",
            "continue pannu", "continue pannunga",
        }:
            return {"success": True, "capability": "resume_project", "payload": {}}

        if text in {"features kaatu", "feature list kaatu", "அம்சங்களை காட்டு", "அம்சங்கள் காட்டு"}:
            return {"success": True, "capability": "list_features", "payload": {}}

        complete_project_phrases = ("build the complete project", "build full project", "build all features")
        if any(phrase in text for phrase in complete_project_phrases):
            return {"success": True, "capability": "project_pipeline", "payload": {"request": command}}

        # A bare app request needs requirements, not a fabricated project plan.
        if text.rstrip(" .!?") in {
            "build an app", "build app", "create an app", "create app",
            "make an app", "make app", "develop an app", "develop app",
        }:
            return {"success": True, "capability": "clarify_project", "payload": {}}

        creation_phrases = (
            "create pannu", "create pannunga", "build pannu", "build pannunga",
            "உருவாக்கு", "உருவாக்குங்கள்", "செயலி உருவாக்கு", "இணையதளம் உருவாக்கு",
        )
        has_english_project_term = any(
            term in text.split()
            for term in ("api", "application", "app", "backend", "project", "website")
        )
        has_tamil_project_term = any(term in text for term in ("செயலி", "இணையதளம்", "திட்டம்"))
        if any(phrase in text for phrase in creation_phrases) and (
            has_english_project_term or has_tamil_project_term
        ):
            return {
                "success": True,
                "capability": "project_generation",
                "payload": {"idea": command},
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

        image_verbs = ("generate", "create", "make", "draw", "render")
        image_nouns = ("image", "picture", "photo", "illustration", "artwork")
        if any(text.startswith(verb) for verb in image_verbs) and any(
            noun in text.split() for noun in image_nouns
        ):
            return {
                "success": True,
                "capability": "generate_image",
                "payload": {"prompt": command, "image_type": "image"},
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

        status_prefixes = (
            "feature status ",
            "status of feature ",
            "check feature ",
        )
        for prefix in status_prefixes:
            if text.startswith(prefix):
                feature = command.strip()[len(prefix):].strip()
                if feature:
                    return {
                        "success": True,
                        "capability": "feature_status",
                        "payload": {"feature": feature},
                    }
                return {"success": False, "message": "Feature name cannot be empty"}

        if text.startswith("is feature ") and text.endswith(" enabled"):
            feature = command.strip()[len("is feature "):-len(" enabled")].strip()
            if feature:
                return {
                    "success": True,
                    "capability": "feature_status",
                    "payload": {"feature": feature},
                }
            return {"success": False, "message": "Feature name cannot be empty"}

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

        if text in {"list features", "list all features", "show features", "show me features"}:
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

        if text == "continue" or text.startswith((
            "continue ",
            "resume my project",
            "resume the project",
            "continue where we stopped",
            "continue where we left off",
        )):
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

        assistant_exact_routes = (
            ("schedule my study session", "scheduling"),
            ("plan my day", "daily_planning"),
            ("notify me when work is done", "notifications"),
            ("organize my work", "personal_organization"),
            ("draft an email to my teacher", "email"),
            ("enable voice assistant", "voice"),
        )
        for phrase, capability in assistant_exact_routes:
            if text == phrase:
                return {"success": True, "capability": capability, "payload": {"request": command}}

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
        if any(phrase in text for phrase in ("upgrade yourself", "improve yourself", "make yourself capable", "add this capability to yourself")):
            return {"success": True, "capability": "self_upgrade_plan", "payload": {"goal": command}}

        if text in {"read system prompt", "show system prompt", "show your instructions", "what are your instructions"}:
            return {"success": True, "capability": "read_system_prompt", "payload": {}}

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
