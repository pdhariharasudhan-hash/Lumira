"""
Deterministic Assistant capability service.
"""

from typing import Any, Dict
import re


class AssistantCapabilityService:

    def scheduling(self, request):
        result = self._result("scheduling", request, "scheduling")
        result["schedule"] = self._extract_schedule(request)
        return result

    def email(self, request):
        result = self._result("email", request, "email assistance")
        result["email_draft"] = self._extract_email_intent(request)
        return result

    def daily_planning(self, request):
        result = self._result("daily_planning", request, "daily planning")
        result["plan"] = self._build_daily_plan(request)
        return result

    def notifications(self, request):
        result = self._result("notifications", request, "notification management")
        result["notification"] = self._extract_notification(request)
        return result

    def voice(self, request):
        result = self._result("voice", request, "voice interaction")
        result["voice_action"] = "capture_or_process_voice_request"
        return result

    def personal_organization(self, request):
        result = self._result("personal_organization", request, "personal organization")
        result["organization"] = self._extract_organization(request)
        return result

    def general_conversation(self, request):
        return self._result("general_conversation", request, "general assistance")

    @staticmethod
    def _extract_schedule(request):
        text = request.strip() if isinstance(request, str) else ""
        match = re.search(r"(?:at|on|by)\s+([^,.]+)", text, re.IGNORECASE)
        return {"action": text, "time_hint": match.group(1).strip() if match else None}

    @staticmethod
    def _extract_email_intent(request):
        text = request.strip() if isinstance(request, str) else ""
        match = re.search(r"(?:to|for)\s+([^,.]+)", text, re.IGNORECASE)
        return {"instruction": text, "recipient_hint": match.group(1).strip() if match else None, "ready_to_send": False}

    @staticmethod
    def _build_daily_plan(request):
        text = request.strip() if isinstance(request, str) else ""
        return {"goal": text, "phases": ["prioritize", "focus", "review"], "requires_task_data": True}

    @staticmethod
    def _extract_notification(request):
        text = request.strip() if isinstance(request, str) else ""
        return {"instruction": text, "requires_trigger": True}

    @staticmethod
    def _extract_organization(request):
        text = request.strip() if isinstance(request, str) else ""
        return {"instruction": text, "status": "ready_for_contextual_organization"}

    @staticmethod
    def _result(capability, request, objective):
        return {
            "success": True,
            "capability": capability,
            "request": request.strip() if isinstance(request, str) else "",
            "objective": objective,
            "steps": [
                "identify request",
                "identify required assistance",
                "prepare response or operation",
                "verify requested outcome",
            ],
            "status": "accept",
        }
