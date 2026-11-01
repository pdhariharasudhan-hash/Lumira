from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from app.services.memory.memory_service import MemoryService, MemoryValidationError


class DecisionLifecycleService:
    """Read and record outcomes for durable personal decision records."""

    OUTCOME_STATES = {"success", "failure", "partial", "reversed"}

    def __init__(self, memory_service=None):
        self.memory = memory_service or MemoryService()

    def get(self, decision_id: str) -> dict | None:
        if not isinstance(decision_id, str) or not decision_id.strip() or len(decision_id) > 128:
            raise MemoryValidationError("decision_id is invalid")
        data = self.memory._read_cognitive_memory()
        for record in data.get("decisions", []):
            if isinstance(record, dict) and record.get("decision_id") == decision_id:
                return deepcopy(record)
        return None

    def record_outcome(self, decision_id: str, outcome_status: str, outcome: str = "") -> dict:
        if outcome_status not in self.OUTCOME_STATES:
            raise MemoryValidationError("unsupported decision outcome status")
        outcome = self.memory._bounded_text(outcome, "outcome", 3000)
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get(decision_id)
        if existing is None:
            raise KeyError("decision not found")
        if existing.get("archived"):
            raise MemoryValidationError("archived decisions cannot receive outcomes")
        first_recording = not bool(existing.get("outcome_recorded_at"))

        def update(document):
            if not isinstance(document, dict) or document.get("schema_version") != 1:
                raise MemoryValidationError("unsupported cognitive memory schema")
            records = document.get("decisions", [])
            target = next(
                (item for item in records if isinstance(item, dict) and item.get("decision_id") == decision_id),
                None,
            )
            if target is None:
                raise KeyError("decision not found")
            if target.get("archived"):
                raise MemoryValidationError("archived decisions cannot receive outcomes")
            target["outcome_status"] = outcome_status
            target["outcome"] = self.memory._safe_text(outcome)
            target["outcome_recorded_at"] = now
            target["status"] = "reviewed"
            return deepcopy(target)

        try:
            decision = self.memory.cognitive_store.update(
                update, self.memory._default_cognitive_memory()
            )
        except KeyError:
            raise
        except Exception as exc:
            if isinstance(exc, MemoryValidationError):
                raise
            raise MemoryValidationError("decision outcome could not be persisted") from exc

        learning_record = None
        # An outcome is observed data, not automatically a verified lesson.
        # It can inform aggregate patterns, but consolidation still requires
        # the user's explicit verification flow.
        if first_recording and outcome_status in {"success", "failure"}:
            learning_record = self.memory.record_experience(
                experience_type=outcome_status,
                summary=f"Decision outcome: {existing.get('decision', '')}"[:4000],
                outcome=outcome or outcome_status,
                project_id=existing.get("project_id"),
                goal_id=existing.get("goal_id"),
                lessons=[],
                source_run=decision_id,
                verified=False,
            )
        return {
            "success": True,
            "decision": decision,
            "outcome_learning": "recorded_unverified" if learning_record else "not_applicable",
        }
