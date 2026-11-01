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

    def _set_learning_status(self, decision_id: str, status: str) -> None:
        def update(document):
            target = next(
                (item for item in document.get("decisions", [])
                 if isinstance(item, dict) and item.get("decision_id") == decision_id),
                None,
            )
            if target is None:
                raise KeyError("decision not found")
            target["outcome_learning_status"] = status
            target["updated_at"] = datetime.now(timezone.utc).isoformat()
            return True

        self.memory.cognitive_store.update(
            update, self.memory._default_cognitive_memory()
        )

    def _ensure_outcome_experience(self, decision: dict) -> str:
        outcome_status = decision.get("outcome_status")
        if outcome_status not in {"success", "failure"}:
            return "not_applicable"
        decision_id = decision["decision_id"]
        cognitive = self.memory._read_cognitive_memory()
        existing = next(
            (item for item in cognitive.get("experiences", [])
             if isinstance(item, dict)
             and item.get("source_run") == decision_id
             and item.get("type") == outcome_status),
            None,
        )
        if existing is None:
            self.memory.record_experience(
                experience_type=outcome_status,
                summary=f"Decision outcome: {decision.get('decision', '')}"[:4000],
                outcome=decision.get("outcome") or outcome_status,
                project_id=decision.get("project_id"),
                goal_id=decision.get("goal_id"),
                lessons=[],
                source_run=decision_id,
                verified=False,
            )
        return "recorded_unverified"

    def record_outcome(self, decision_id: str, outcome_status: str, outcome: str = "") -> dict:
        if outcome_status not in self.OUTCOME_STATES:
            raise MemoryValidationError("unsupported decision outcome status")
        outcome = "" if outcome == "" else self.memory._bounded_text(outcome, "outcome", 3000)
        existing = self.get(decision_id)
        if existing is None:
            raise KeyError("decision not found")
        if existing.get("archived"):
            raise MemoryValidationError("archived decisions cannot receive outcomes")

        if existing.get("outcome_recorded_at"):
            if (
                existing.get("outcome_status") != outcome_status
                or existing.get("outcome", "") != outcome
            ):
                raise MemoryValidationError(
                    "decision outcome is already recorded; create a new decision to record a changed outcome"
                )
            # Idempotent retry: repair a pending/failed learning side effect
            # without duplicating an already persisted experience.
            try:
                learning_status = self._ensure_outcome_experience(existing)
                self._set_learning_status(decision_id, learning_status)
            except Exception:
                learning_status = "recording_failed"
            return {
                "success": True,
                "idempotent": True,
                "decision": self.get(decision_id),
                "outcome_learning": learning_status,
            }

        now = datetime.now(timezone.utc).isoformat()

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
            if target.get("outcome_recorded_at"):
                raise MemoryValidationError("decision outcome is already recorded")
            target["outcome_status"] = outcome_status
            target["outcome"] = self.memory._safe_text(outcome)
            target["outcome_recorded_at"] = now
            target["outcome_learning_status"] = (
                "pending" if outcome_status in {"success", "failure"} else "not_applicable"
            )
            target["status"] = "reviewed"
            target["updated_at"] = now
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

        try:
            learning_status = self._ensure_outcome_experience(decision)
            self._set_learning_status(decision_id, learning_status)
        except Exception:
            # The decision outcome is already durable; expose a retryable
            # secondary-write failure without misreporting the primary update.
            learning_status = "recording_failed"
        return {
            "success": True,
            "decision": self.get(decision_id),
            "outcome_learning": learning_status,
        }
