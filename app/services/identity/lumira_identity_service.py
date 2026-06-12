import re
from typing import Dict, Any


class LumiraIdentityService:

    ACTIVATION_KEYWORDS = {
        "activate": "activate",
        "enable": "activate",

        "disable": "disable",
        "deactivate": "disable"
    }

    FEATURE_ALIASES = {

        "voice idea capture":
        "voice_idea_capture",

        "voice capture":
        "voice_idea_capture",

        "artifact manager":
        "artifact_manager",

        "image generation":
        "image_generation",

        "unified search":
        "unified_search",

        "memory":
        "memory",

        "voice input":
        "voice_input"
    }

    def parse(
        self,
        text: str
    ) -> Dict[str, Any]:

        original = text

        text = text.strip()

        if not text:

            return {
                "recognized": False,
                "reason": "empty_input"
            }

        normalized = text.lower()

        normalized = re.sub(
            r"^lumira[\s,:-]*",
            "",
            normalized
        )

        parts = normalized.split()

        if not parts:

            return {
                "recognized": False,
                "reason": "no_command"
            }

        command_word = parts[0]

        if command_word not in self.ACTIVATION_KEYWORDS:

            return {
                "recognized": False,
                "reason": "unsupported_command"
            }

        command = (
            self.ACTIVATION_KEYWORDS[
                command_word
            ]
        )

        feature_text = " ".join(
            parts[1:]
        ).strip()

        if not feature_text:

            return {
                "recognized": False,
                "reason": "missing_feature"
            }

        feature = (
            self.FEATURE_ALIASES.get(
                feature_text
            )
        )

        if not feature:

            return {
                "recognized": False,
                "reason": "unknown_feature",
                "feature_text": feature_text
            }

        return {
            "recognized": True,
            "assistant": "lumira",
            "command": command,
            "target": feature,
            "original_input": original
        }

    def is_lumira_command(
        self,
        text: str
    ) -> bool:

        if not text:
            return False

        return text.strip().lower().startswith(
            "lumira"
        )