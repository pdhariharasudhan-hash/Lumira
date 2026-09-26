# core/services/project_classifier.py
from typing import Dict, List
import re


class ProjectClassifier:

    def extract_entities(
        self,
        text: str
    ) -> List[str]:

        words = re.findall(
            r"\b[a-zA-Z]+\b",
            text.lower()
        )

        ignore = {
            "build",
            "create",
            "make",
            "generate",
            "a",
            "an",
            "the",
            "simple",
            "basic",
            "api",
            "app",
            "tracker",
            "backend",
            "system",
            "fastapi",
            "flask",
            "django",
            "express",
            "node",
            "react",
            "rest",
            "authentication",
            "authorization",
            "auth",
            "jwt",
            "login",
            "test",
            "tests",
            "testing",
            "secure",
            "with",
            "for",
        }

        entities = []

        for word in words:

            if word not in ignore:

                entities.append(
                    word
                )

        return entities

    def detect_actions(
        self,
        text: str
    ) -> List[str]:

        text = text.lower()

        actions = []

        api_words = [
            "api",
            "tracker",
            "manager",
            "crud"
        ]

        for word in api_words:

            if word in text:

                actions.extend([
                    "storage",
                    "create",
                    "read",
                    "update",
                    "delete"
                ])

                break

        # LUMIRA CAPABILITY ACTION ALIASES
        if isinstance(text, str):
            _lumira_input = text.strip().lower()

            # Debugging requires executable project actions.
            if "debug" in _lumira_input:
                for _lumira_action in (
                    "storage",
                    "read",
                    "update",
                    "delete",
                ):
                    if _lumira_action not in actions:
                        actions.append(_lumira_action)

            # Project generation requires executable creation steps.
            if "create" in _lumira_input and "project" in _lumira_input:
                if "storage" not in actions:
                    actions.append("storage")
                if "create" not in actions:
                    actions.append("create")
        return list(
            set(actions)
        )

    def detect_type(
        self,
        text: str
    ) -> str:

        text = text.lower()

        api_patterns = [
            "api",
            "backend",
            "tracker"
        ]

        for item in api_patterns:

            if item in text:

                return "api"

        return "generic"

    def primary_entity(
        self,
        entities: List[str]
    ) -> str:

        if len(
            entities
        ) == 0:

            return "item"

        return entities[0]

    def classify(
        self,
        idea: str
    ) -> Dict:

        project_type = self.detect_type(
            idea
        )

        entities = self.extract_entities(
            idea
        )

        actions = self.detect_actions(
            idea
        )

        return {

            "input":
            idea,

            "project_type":
            project_type,

            "entities":
            entities,

            "primary_entity":
            self.primary_entity(
                entities
            ),

            "actions":
            actions,

            "confidence":
            "medium"
        }
