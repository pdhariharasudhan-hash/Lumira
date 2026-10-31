class CheckpointSessionGuardService:
    """Validate that a recovery checkpoint belongs to a resumable session."""

    def __init__(self, session_service):
        self.session_service = session_service

    def evaluate(self, session_id, run):
        session = self.session_service.get_session(session_id)
        if session is None:
            raise KeyError("session not found")
        linked = run.get("session_id") == session_id
        active = session.get("status") == "active"
        return {
            "success": True,
            "session_id": session_id,
            "session_status": session.get("status"),
            "session_linked": linked,
            "session_active": active,
            "allowed": linked and active,
            "reason": None if linked and active else (
                "session_run_mismatch" if not linked else "session_not_active"
            ),
        }
