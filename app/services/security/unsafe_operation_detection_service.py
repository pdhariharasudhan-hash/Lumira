from __future__ import annotations

import re
from typing import Any


class UnsafeOperationDetectionService:
    """Conservative, deterministic preflight checks for risky instructions."""

    _RULES = (
        ("credential_exfiltration", re.compile(r"\b(?:dump|exfiltrate|print|send|leak)\b.{0,80}\b(?:password|secret|api[_ -]?key|token|credential)\b", re.I)),
        ("destructive_filesystem", re.compile(r"\b(?:format|wipe|erase|delete)\b.{0,80}\b(?:drive|disk|all files|entire directory|root)\b", re.I)),
        ("unsafe_privilege_change", re.compile(r"\b(?:disable|bypass|turn off)\b.{0,80}\b(?:security|firewall|antivirus|permission|sandbox)\b", re.I)),
        ("unapproved_external_action", re.compile(r"\b(?:deploy|publish|send email|transfer money|purchase)\b", re.I)),
    )

    @classmethod
    def analyze(cls, instruction: str) -> dict[str, Any]:
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction.strip()) > 10_000:
            return {"success": False, "code": "invalid_instruction", "allowed": False, "findings": []}
        findings = [
            {"rule": rule, "severity": "high", "action": "require_explicit_approval"}
            for rule, pattern in cls._RULES
            if pattern.search(instruction)
        ]
        return {
            "success": True,
            "allowed": not findings,
            "action": "allow" if not findings else "block_pending_approval",
            "findings": findings,
        }
