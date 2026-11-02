class CheckpointResumeOrchestratorService:
    """Bridge checkpoint preflight into an existing guarded resume callable."""

    def __init__(self, preflight_service, dedup_service, event_service, gate_service):
        self.preflight_service = preflight_service
        self.dedup_service = dedup_service
        self.event_service = event_service
        self.gate_service = gate_service

    def prepare(self, session_id, run, request_id, previous_request_ids=None):
        preflight = self.preflight_service.evaluate(session_id, run)
        deduplication = self.dedup_service.evaluate(
            run.get("run_id"), request_id, previous_request_ids
        )
        gate = self.gate_service.evaluate(preflight, deduplication)
        event = self.event_service.build(session_id, run.get("run_id"), preflight, deduplication)
        return {
            "success": True,
            "preflight": preflight,
            "deduplication": deduplication,
            "gate": gate,
            "event": event,
        }
