class CheckpointResumePreflightReportService:
    """Expose a minimal, stable report without leaking full run internals."""

    def report(self, prepared):
        preflight = prepared.get("preflight", {})
        decision = preflight.get("decision", {})
        command = preflight.get("command", {})
        return {
            "success": True,
            "resume_candidate": decision.get("resume_candidate", False),
            "safe_resume_point": command.get("safe_resume_point"),
            "duplicate": prepared.get("deduplication", {}).get("duplicate", False),
            "execute_resume": prepared.get("gate", {}).get("execute_resume", False),
            "reason": prepared.get("gate", {}).get("reason"),
        }
