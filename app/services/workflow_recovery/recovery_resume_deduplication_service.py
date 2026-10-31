class RecoveryResumeDeduplicationService:
    """Reject duplicate resume requests using explicit caller-supplied request history."""

    def evaluate(self, run_id, request_id, previous_request_ids):
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("request_id is required")
        seen = set(previous_request_ids or [])
        duplicate = request_id in seen
        return {
            "success": True,
            "run_id": run_id,
            "request_id": request_id,
            "duplicate": duplicate,
            "resume_allowed": not duplicate,
            "reason": "duplicate_resume_request" if duplicate else None,
        }
