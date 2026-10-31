class CheckpointResumeHistoryService:
    """Keep bounded request identifiers for callers that persist recovery history."""

    MAX_REQUEST_IDS = 100

    def append(self, previous_request_ids, request_id):
        history = list(previous_request_ids or [])
        if request_id not in history:
            history.append(request_id)
        return history[-self.MAX_REQUEST_IDS:]
