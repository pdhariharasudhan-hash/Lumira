"""
brain_service.py

Main entry point for Lumira's Intelligence Layer.

BrainService coordinates the complete Brain execution flow.

It does not contain cognitive intelligence itself.

Flow:

BrainRequest
    ?
BrainState
    ?
Command History
    ?
BrainValidator
    ?
BrainPipeline
    ?
BrainExecutor
    ?
Pipeline History
    ?
BrainResponse

Ownership:
Handoff 12 - Brain Integration
"""

from typing import Optional

from app.services.brain.brain_factory import (
    BrainFactory,
)

from app.services.brain.brain_request import (
    BrainRequest,
)

from app.services.brain.brain_response import (
    BrainResponse,
)

from app.services.brain.brain_state import (
    BrainState,
)

from app.services.modes.mode_detection_service import (
    ModeDetectionService,
)

from app.services.modes.mode_manager_service import (
    ModeManagerService,
)

from app.services.history.command_history_service import (
    CommandHistoryService,
)

from app.services.history.pipeline_history_service import (
    PipelineHistoryService,
)
from app.services.memory.memory_service import MemoryService
from app.services.sessions.session_manager_service import (
    SessionManagerService,
    redact_sensitive_text,
    redact_sensitive_value,
)
from app.services.conversation.conversation_models import ConversationState
from app.services.goals.goal_models import GoalState
from app.services.objective.objective_models import ObjectiveState
from app.services.history.event_logger_service import EventLoggerService
from app.services.language.intent_classifier_service import IntentClassifierService
from app.services.resources.resource_budget_service import ResourceBudgetService


class BrainService:
    """
    Main public orchestrator for Lumira's Brain.
    """

    def __init__(self) -> None:

        components = (
            BrainFactory.create_brain_components()
        )

        self.registry = components["registry"]

        self.executor = components["executor"]

        self.validator = components["validator"]

        self.pipeline = (
            self._create_pipeline()
        )

        self.command_history = (
            CommandHistoryService()
        )

        self.pipeline_history = (
            PipelineHistoryService()
        )

        self.mode_detector = (
            ModeDetectionService()
        )

        self.sessions = SessionManagerService()
        self.memory = MemoryService()
        self.intent_classifier = IntentClassifierService()

    def _create_pipeline(self):
        """
        Create the BrainPipeline using the shared executor.
        """

        from app.services.brain.brain_pipeline import (
            BrainPipeline,
        )

        return BrainPipeline(
            executor=self.executor
        )

    def create_state(
        self,
        request: Optional[BrainRequest] = None,
    ) -> BrainState:
        """
        Create a fresh temporary BrainState.

        Request-level information is propagated into
        the BrainState and its execution context.
        """

        state = BrainState()

        if request is None:
            return state

        state.user_input = request.message
        state.intent = self.intent_classifier.classify(request.message)

        state.execution_context.update(
            session_id=request.session_id,
            project_id=request.project or "",
            environment=request.environment,
            workspace=request.workspace,
            metadata=dict(request.metadata),
        )

        return state

    def _resolve_mode(
        self,
        state: BrainState,
    ) -> None:
        """
        Resolve the operating mode for one Brain request.

        Mode detection is reusable and deterministic.

        Mode management is deliberately request-local so
        one Brain execution cannot leak its active mode
        into another independent execution.
        """

        if not state.user_input.strip():
            return

        preferred_mode = state.execution_context.metadata.get(
            "active_mode"
        )

        if preferred_mode and self.mode_detector.registry.exists(preferred_mode):
            mode_manager = ModeManagerService()
            mode_manager.activate(
                mode_id=preferred_mode,
                reason="persisted_manual_selection",
                confidence=1.0,
                manual=True,
            )
            state.mode = mode_manager.get_state().model_copy(deep=True)
            return

        detection = self.mode_detector.detect(
            state.user_input
        )

        if not detection.selected_mode:
            return

        mode_manager = ModeManagerService()

        mode_manager.activate(
            mode_id=detection.selected_mode,
            reason="mode_detection",
            confidence=detection.top_score,
            manual=False,
        )

        state.mode = (
            mode_manager
            .get_state()
            .model_copy(
                deep=True
            )
        )

    def _record_command(
        self,
        state: BrainState,
    ) -> None:
        """
        Record the incoming command using the current
        BrainState execution identity.
        """

        context = state.execution_context

        self.command_history.record(
            request_id=context.request_id,
            execution_id=context.execution_id,
            session_id=context.session_id,
            project_id=context.project_id,
            message=redact_sensitive_text(state.user_input),
            environment=context.environment,
            workspace=context.workspace,
            metadata=dict(context.metadata),
        )

    def _record_pipeline(
        self,
        state: BrainState,
        success: bool,
        trace: list,
        error: Optional[str] = None,
    ) -> None:
        """
        Record the completed or failed pipeline using
        the SAME BrainState execution identity.
        """

        context = state.execution_context

        self.pipeline_history.record(
            execution_id=context.execution_id,
            request_id=context.request_id,
            session_id=context.session_id,
            project_id=context.project_id,
            user_input=redact_sensitive_text(state.user_input),
            success=success,
            trace=redact_sensitive_value(trace),
            error=error,
        )

    def validate(
        self,
        state: BrainState,
    ) -> dict:
        """
        Validate the Brain registry and current state.
        """

        return self.validator.validate(
            self.registry,
            state,
        )

    def execute(
        self,
        request: Optional[BrainRequest] = None,
    ) -> BrainResponse:
        """
        Execute one complete Brain request.

        One request creates exactly one BrainState.
        That same state owns the execution identity used
        by command history and pipeline history.
        """

        request = request or BrainRequest()
        session = self.sessions.resolve_session(
            session_id=request.session_id or None,
            workspace_id=request.workspace,
            project_id=request.project,
        )
        request = request.model_copy(update={
            "session_id": session["session_id"],
            "project": request.project or session.get("active_project"),
            "metadata": {
                **request.metadata,
                "active_mode": session.get("active_mode") or request.metadata.get("active_mode"),
            },
        })

        state = self.create_state(request)
        self._restore_session_state(state, session)
        state.relevant_memory = self.memory.retrieve_relevant(
            query=request.message,
            project_id=session.get("active_project") or request.project,
            goal_id=session.get("goal_id"),
        )
        # Resource guidance is compact and advisory; telemetry failure must never
        # prevent the main cognitive pipeline from processing the request.
        try:
            state.relevant_memory["resource_budget"] = (
                ResourceBudgetService().execution_guidance()
            )
        except Exception:
            state.relevant_memory["resource_budget_status"] = "unavailable"

        # An explicitly linked session goal is authoritative context even when
        # its title does not happen to match the user's current query terms.
        active_goal_id = session.get("goal_id")
        if isinstance(active_goal_id, str) and active_goal_id:
            goal_records = self.memory.get_all().get("goals", [])
            active_goal = next(
                (
                    item for item in goal_records
                    if isinstance(item, dict) and item.get("goal_id") == active_goal_id
                ),
                None,
            )
            if active_goal is not None:
                goal_context = {
                    key: active_goal.get(key)
                    for key in (
                        "goal_id", "title", "objective", "status", "priority",
                        "progress", "deadline", "dependencies", "blockers", "project_id",
                    )
                }
                state.relevant_memory["active_goal"] = redact_sensitive_value(goal_context)
                if not state.goal.primary_goal.strip():
                    state.goal = GoalState(
                        primary_goal=str(active_goal.get("title") or ""),
                        priority=str(active_goal.get("priority") or "normal"),
                        completed=active_goal.get("status") == "completed",
                        confidence=1.0,
                    )
                if not state.objective.primary_objective.strip() and active_goal.get("objective"):
                    state.objective = ObjectiveState(
                        primary_objective=str(active_goal.get("objective"))[:2000],
                        confidence=1.0,
                        completion_status="completed" if active_goal.get("progress") == 100 else "in_progress",
                    )
        # Explicit decisions are durable constraints, not merely search results.
        # Load only recent decisions relevant to this session/project/goal.
        try:
            decision_records = self.memory.get_all().get("decisions", [])
            if isinstance(decision_records, list):
                active_project_id = session.get("active_project") or request.project
                relevant_decisions = []
                for decision in decision_records:
                    if not isinstance(decision, dict) or decision.get("archived"):
                        continue
                    if decision.get("session_id") == session.get("session_id"):
                        relevant_decisions.append(decision)
                    elif active_goal_id and decision.get("goal_id") == active_goal_id:
                        relevant_decisions.append(decision)
                    elif active_project_id and decision.get("project_id") == active_project_id:
                        relevant_decisions.append(decision)
                state.relevant_memory["decisions"] = redact_sensitive_value([
                    {
                        key: decision.get(key)
                        for key in (
                            "decision_id", "decision", "reason", "alternatives",
                            "constraints", "confidence", "created_at", "project_id", "goal_id",
                        )
                    }
                    for decision in relevant_decisions[-10:]
                ])
        except Exception:
            # Optional decision context must not stop the primary brain pipeline.
            state.relevant_memory["decisions_context_status"] = "unavailable"

        # Preserve explicit memory relationships around the active goal and decisions.
        try:
            all_memory = self.memory.get_all()
            links = all_memory.get("memory_links", [])
            relevant_ids = {active_goal_id} if isinstance(active_goal_id, str) and active_goal_id else set()
            current_decisions = state.relevant_memory.get("decisions", [])
            if isinstance(current_decisions, list):
                relevant_ids.update(
                    item.get("decision_id") for item in current_decisions
                    if isinstance(item, dict) and isinstance(item.get("decision_id"), str)
                )
            if isinstance(links, list):
                state.relevant_memory["memory_relationships"] = redact_sensitive_value([
                    {
                        "source_id": link.get("source_id"),
                        "target_id": link.get("target_id"),
                        "relation": link.get("relation"),
                    }
                    for link in links
                    if isinstance(link, dict)
                    and (link.get("source_id") in relevant_ids or link.get("target_id") in relevant_ids)
                ][-20:])
        except Exception:
            state.relevant_memory["memory_relationships_status"] = "unavailable"

        # Rehydrate a compact recovery slice rather than replaying the whole session.
        snapshots = session.get("context_snapshots", [])
        if isinstance(snapshots, list) and snapshots and isinstance(snapshots[-1], dict):
            latest = snapshots[-1]
            state.relevant_memory["session_recovery"] = {
                "created_at": latest.get("created_at"),
                "active_project": latest.get("active_project"),
                "active_version": latest.get("active_version"),
                "active_mode": latest.get("active_mode"),
                "current_goal": latest.get("current_goal"),
                "goal_id": latest.get("goal_id"),
                "workflows": [
                    item for item in latest.get("workflows", [])[:10]
                    if isinstance(item, dict)
                ] if isinstance(latest.get("workflows", []), list) else [],
                "pending_tasks": [
                    item for item in latest.get("pending_tasks", [])[:10]
                    if isinstance(item, dict)
                ] if isinstance(latest.get("pending_tasks", []), list) else [],
                "blockers": latest.get("blockers", [])[:20]
                if isinstance(latest.get("blockers", []), list) else [],
            }
        EventLoggerService().log(
            event="memory_retrieved",
            source="brain",
            data={
                "session_id": session["session_id"],
                "record_counts": {
                    key: len(value) for key, value in state.relevant_memory.items()
                },
            },
        )
        if session.get("cognitive_state"):
            EventLoggerService().log(
                event="context_restored",
                source="brain",
                data={"session_id": session["session_id"]},
            )

        # ----------------------------------
        # Resolve operating mode
        # ----------------------------------

        self._resolve_mode(
            state
        )

        # ----------------------------------
        # Record incoming command
        # ----------------------------------

        self._record_command(
            state
        )

        # ----------------------------------
        # Initial validation
        # ----------------------------------

        validation = self.validate(
            state
        )

        if not validation["valid"]:

            error = redact_sensitive_text(str(validation))

            self._record_pipeline(
                state=state,
                success=False,
                trace=[],
                error=error,
            )

            self._persist_run(state, session, success=False, error=error)

            return BrainResponse(
                success=False,
                state=state,
                error=error,
            )

        # ----------------------------------
        # Brain Pipeline
        # ----------------------------------

        trace = []

        try:

            result = (
                self.pipeline.execute_with_trace(
                    state
                )
            )

            final_state = result["state"]

            trace = result["trace"]

        except Exception as exc:

            error = redact_sensitive_text(f"{type(exc).__name__}: {exc}")
            trace = redact_sensitive_value(trace)

            self._record_pipeline(
                state=state,
                success=False,
                trace=trace,
                error=error,
            )

            self._persist_run(state, session, success=False, error=error)

            return BrainResponse(
                success=False,
                state=state,
                trace=trace,
                error=error,
            )

        # A verification rejection is terminal and must not be converted into success.
        if final_state.status == "rejected":
            error = redact_sensitive_text("Verification rejected execution")
            self._record_pipeline(
                state=final_state,
                success=False,
                trace=trace,
                error=error,
            )
            self._persist_run(final_state, session, success=False, error=error)
            return BrainResponse(
                success=False,
                state=final_state,
                trace=trace,
                error=error,
            )

        # ----------------------------------
        # Final validation
        # ----------------------------------

        final_validation = (
            self.validator.validate_state(
                final_state
            )
        )

        if not final_validation["valid"]:

            error = redact_sensitive_text(str(final_validation))

            self._record_pipeline(
                state=final_state,
                success=False,
                trace=trace,
                error=error,
            )

            self._persist_run(final_state, session, success=False, error=error)

            return BrainResponse(
                success=False,
                state=final_state,
                trace=trace,
                error=error,
            )

        # ----------------------------------
        # Successful pipeline history
        # ----------------------------------

        self._record_pipeline(
            state=final_state,
            success=True,
            trace=trace,
            error=None,
        )

        self._persist_run(final_state, session, success=True)

        return BrainResponse(
            success=True,
            state=final_state,
            trace=trace,
        )

    def _publish_execution_outcome(self, state, session: dict, success: bool) -> None:
        """Publish a compact execution outcome when event integrations are available."""
        if self.core_events is None or self.notifications is None:
            return
        event_name = "brain_execution_completed" if success else "brain_execution_failed"
        try:
            recorded = self.core_events.record(
                event_name,
                "brain",
                session_id=session.get("session_id"),
                project_id=session.get("active_project"),
                goal_id=session.get("goal_id"),
                execution_id=getattr(state.execution_context, "execution_id", None),
            )
            event = recorded.get("event_record", recorded) if isinstance(recorded, dict) else recorded
            self.notifications.create_from_core_event(event)
        except Exception:
            # Event delivery is secondary and must not break the brain result.
            return

    def _restore_session_state(self, state: BrainState, session: dict) -> None:
        conversation = session.get("conversation", {})
        cognitive = session.get("cognitive_state") or {}
        state.conversation = ConversationState(
            session_id=session["session_id"],
            conversation_id=session.get("conversation_id", ""),
            current_topic=conversation.get("current_topic", ""),
            current_goal=session.get("current_goal") or "",
            conversation_summary=conversation.get("summary", ""),
            pending_questions=conversation.get("pending_questions", []),
            topic_history=[
                message["content"]
                for message in session.get("recent_messages", [])
                if message.get("role") == "user"
            ][-20:],
            recent_messages=session.get("recent_messages", [])[-20:],
            recent_references=conversation.get("recent_references", []),
            detected_language=conversation.get("language_context", "en"),
        )
        if cognitive.get("goal"):
            state.goal = GoalState(
                primary_goal=cognitive["goal"],
                confidence=float(cognitive.get("confidence") or 0.0),
            )
        if cognitive.get("objective"):
            state.objective = ObjectiveState(
                primary_objective=cognitive["objective"],
                confidence=float(cognitive.get("confidence") or 0.0),
                completion_status="in_progress",
            )
        state.execution_context.project_id = session.get("active_project") or ""

    def _persist_run(self, state: BrainState, session: dict, success: bool, error: str | None = None) -> None:
        session_id = session["session_id"]
        if state.user_input:
            self.sessions.append_message(session_id, "user", state.user_input)

        goal = state.goal.primary_goal.strip()
        goal_id = session.get("goal_id")
        if goal_id:
            EventLoggerService().log(
                event="goal_loaded",
                source="brain",
                data={"session_id": session_id, "goal_id": goal_id},
            )
        if goal:
            if goal_id:
                self.memory.update_goal(
                    goal_id,
                    title=goal,
                    objective=state.objective.primary_objective,
                    project_id=session.get("active_project"),
                    status="active",
                    blockers=(
                        list(state.constraints.missing_information)
                        + list(state.constraints.risks)
                    ),
                )
            else:
                goal_record = self.memory.create_goal(
                    title=goal,
                    objective=state.objective.primary_objective,
                    priority=state.goal.priority,
                    project_id=session.get("active_project"),
                    blockers=(
                        list(state.constraints.missing_information)
                        + list(state.constraints.risks)
                    ),
                )
                goal_id = goal_record["goal_id"]

        state_dict = state.model_dump(mode="json")
        self.sessions.save_cognitive_state(
            session_id,
            state_dict,
            goal_id=goal_id,
            success=success,
        )
        self.sessions.update_context(
            session_id,
            project_id=session.get("active_project"),
            active_project=session.get("active_project"),
            active_version=session.get("active_version"),
            active_mode=state.mode.active_mode,
            current_goal=goal or session.get("current_goal"),
            goal_id=goal_id,
        )

        if goal and not success:
            experience = self.memory.record_experience(
                "failure",
                summary=f"{state.objective.primary_objective or goal}",
                outcome=f"cognitive pipeline failed: {error or 'unknown error'}",
                project_id=session.get("active_project"),
                goal_id=goal_id,
                source_run=state.execution_context.execution_id,
            )
            self.sessions.link_record(
                session_id,
                "experience",
                experience["experience_id"],
            )
            EventLoggerService().log(
                event="experience_created",
                source="brain",
                data={"session_id": session_id, "experience_id": experience["experience_id"]},
            )

    def get_modules(self):
        """
        Return all registered Intelligence modules.
        """

        return self.registry.get_modules()

    def get_execution_order(self):
        """
        Return the deterministic Intelligence execution order.
        """

        return self.executor.get_execution_order()

    def get_stage_names(self):
        """
        Return the pipeline stage names.
        """

        return self.pipeline.get_stage_names()

    def total_stages(self) -> int:
        """
        Return the number of enabled Brain stages.
        """

        return self.pipeline.total_stages()
