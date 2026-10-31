class CheckpointResumePreflightService:
    """Run all checkpoint guards before a resume command is considered."""

    def __init__(self, session_guard, integrity_service, decision_service, command_service):
        self.session_guard = session_guard
        self.integrity_service = integrity_service
        self.decision_service = decision_service
        self.command_service = command_service

    def evaluate(self, session_id, run):
        session_guard = self.session_guard.evaluate(session_id, run)
        integrity = self.integrity_service.evaluate(run)
        decision = self.decision_service.decide(session_guard, integrity)
        command = self.command_service.build(decision, run.get("run_id"))
        return {
            "success": True,
            "session_guard": session_guard,
            "checkpoint_integrity": integrity,
            "decision": decision,
            "command": command,
        }
