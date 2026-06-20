from typing import Dict, Any

from app.services.projects.project_classifier import (
    ProjectClassifier
)

from app.services.code.naming_service import (
    NamingService
)


class BuilderService:

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
                            "step_1"
                        ]
                    }
                )

                step_number += 1

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