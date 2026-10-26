from typing import Dict, Any

from app.services.projects.project_classifier import (
    ProjectClassifier
)

from app.services.code.naming_service import (
    NamingService
)


class BuilderService:

    MAX_INPUT_LENGTH = 10000
    MAX_PLAN_STEPS = 12

    def __init__(
        self
    ):

        self.classifier = (
            ProjectClassifier()
        )

        self.naming = (
            NamingService()
        )

    def build(
        self,
        idea: str
    ) -> Dict[str, Any]:

        if not isinstance(idea, str) or not idea.strip() or len(idea) > self.MAX_INPUT_LENGTH:
            return {
                "objective": "",
                "scope": "small",
                "suggested_steps": [],
                "priority": "high",
                "status": "refine",
                "reasons": ["Provide a non-empty objective under 10000 characters."],
            }

        from app.routes.validate import analyze_idea

        validation = analyze_idea(idea)
        if validation["verdict"] == "reject":
            return {
                "objective": idea.strip(),
                "scope": "undetermined",
                "suggested_steps": [],
                "priority": "high",
                "status": "refine",
                "reasons": validation["weaknesses"] + validation["risks"],
                "validation": validation,
            }

        result = (
            self.classifier.classify(
                idea
            )
        )

        entity = result[
            "primary_entity"
        ]

        collection_name = (
            self.naming
            .pluralize(
                entity
            )
        )

        actions = result[
            "actions"
        ]

        suggested_steps = []

        step_number = 1

        storage_step_id = None
        if "storage" in actions:

            suggested_steps.append(
                {
                    "id":
                    f"step_{step_number}",

                    "action":
                    f"create {entity} storage",

                    "inputs": {},

                    "expected_output":
                    f"{collection_name} initialized",

                    "dependencies": []
                }
            )

            step_number += 1
            storage_step_id = "step_1"

        route_map = {

            "create": "POST",
            "read": "GET",
            "update": "PUT",
            "delete": "DELETE"
        }

        for action, http in route_map.items():

            if action in actions:

                suggested_steps.append(
                    {
                        "id":
                        f"step_{step_number}",

                        "action":
                        f"implement {entity} {http} route",

                        "inputs": {},

                        "expected_output":
                        f"{entity} {http} endpoint created",

                        "dependencies": [
                            storage_step_id
                        ] if storage_step_id else []
                    }
                )

                step_number += 1

        if not suggested_steps or len(suggested_steps) > self.MAX_PLAN_STEPS:
            return {
                "idea": idea,
                "objective": f"build {entity} api",
                "scope": "small",
                "suggested_steps": [],
                "priority": "high",
                "status": "refine",
                "reasons": ["The request does not map to an executable project plan."],
            }

        return {

            "idea":
            idea,

            "objective":
            f"build {entity} api",

            "scope":
            "small",

            "suggested_steps":
            suggested_steps,

            "priority":
            "high",

            "status":
            "accept"
        }
