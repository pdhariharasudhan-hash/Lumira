"""Central router registry for Lumira.

Keep route imports and application router wiring out of app.main so the
application entry point remains focused on startup, security and middleware.
"""

from app.routes.builder import router as builder_router
from app.routes.code import router as code_router
from app.routes.execute import router as execute_router
from app.routes.validate import router as validate_router
from app.routes.memory import router as memory_router
from app.routes.memory_links import router as memory_links_router
from app.routes.health import router as health_router
from app.routes.resources import router as resources_router
from app.routes.brain import router as brain_router
from app.routes.run import router as run_router
from app.routes.projects import router as projects_router
from app.routes.project_insights import router as project_insights_router
from app.routes.project_details import router as project_details_router
from app.routes.continue_project import router as continue_router
from app.routes.compare import router as compare_router
from app.routes.project_versions import router as project_versions_router
from app.routes.project_files import router as project_files_router
from app.routes.project_file_content import router as project_file_content_router
from app.routes.search import router as search_router
from app.routes.voice_capture import router as voice_capture_router
from app.routes.artifacts import router as artifacts_router
from app.routes.command import router as command_router
from app.routes.sessions import router as sessions_router
from app.routes.session_insights import router as session_insights_router
from app.routes.goals import router as goals_router
from app.routes.goal_intelligence import router as goal_intelligence_router
from app.routes.agents import router as agents_router
from app.routes.workflows import router as workflows_router
from app.routes.workflow_insights import router as workflow_insights_router
from app.routes.auth import router as auth_router
from app.routes.devices import router as devices_router
from app.routes.project_terminal import router as project_terminal_router
from app.routes.project_preview import router as project_preview_router
from app.routes.web import router as web_router
from app.routes.recovery import router as recovery_router
from app.routes.features import router as features_router
from app.routes.intelligence import router as intelligence_router
from app.routes.notepad import router as notepad_router
from app.routes.image_understanding import router as image_understanding_router
from app.routes.image_generation import router as image_generation_router
from app.routes.research_library import router as research_library_router
from app.routes.research_compare import router as research_compare_router
from app.routes.text_ideas import router as text_ideas_router
from app.routes.idea_planning import router as idea_planning_router
from app.routes.voice_history import router as voice_history_router
from app.routes.circuit_planning import router as circuit_planning_router
from app.routes.microcontroller_projects import router as microcontroller_projects_router
from app.routes.project_documentation import router as project_documentation_router
from app.routes.ai_modes import router as ai_modes_router
from app.routes.personal_preferences import router as personal_preferences_router
from app.routes.device_profiles import router as device_profiles_router
from app.routes.recovery_checkpoints import router as recovery_checkpoints_router
from app.routes.personal_context import router as personal_context_router
from app.routes.knowledge import router as knowledge_router
from app.routes.personal_library import router as personal_library_router
from app.routes.electronics_assistant import router as electronics_assistant_router
from app.routes.personal_todos import router as personal_todos_router
from app.routes.system_status import router as system_status_router
from app.routes.core_features import router as core_features_router
from app.routes.core_runtime import router as core_runtime_router
from app.routes.reminders import router as reminders_router
from app.routes.notifications import router as notifications_router
from app.routes.quick_tasks import router as quick_tasks_router
from app.routes.task_insights import router as task_insights_router
from app.routes.core_events import router as core_events_router
from app.routes.system_health import router as system_health_router
from app.routes.core_diagnostics import router as core_diagnostics_router
from app.routes.goal_insights import router as goal_insights_router
from app.routes.next_actions import router as next_actions_router
from app.routes.personal_briefing import router as personal_briefing_router
from app.routes.decision_context import router as decision_context_router
from app.routes.decision_lifecycle import router as decision_lifecycle_router
from app.routes.action_priority import router as action_priority_router
from app.routes.core_activity_summary import router as core_activity_summary_router
from app.routes.briefing_priorities import router as briefing_priorities_router
from app.routes.core_attention import router as core_attention_router
from app.routes.execution_loop import router as execution_loop_router
from app.routes.blocker_queue import router as blocker_queue_router
from app.routes.blocker_insights import router as blocker_insights_router
from app.routes.execution_readiness import router as execution_readiness_router
from app.routes.core_intelligence import router as core_intelligence_router
from app.routes.action_summary import router as action_summary_router
from app.routes.execution_feedback import router as execution_feedback_router
from app.routes.outcome_insights import router as outcome_insights_router
from app.routes.execution_review import router as execution_review_router
from app.routes.outcome_learning import router as outcome_learning_router
from app.routes.learning_loop import router as learning_loop_router
from app.routes.recovery_intelligence import router as recovery_intelligence_router
from app.routes.workflow_recovery import router as workflow_recovery_router
from app.routes.task_recovery import router as task_recovery_router
from app.routes.task_recovery_plan import router as task_recovery_plan_router
from app.routes.recovery_resume import router as recovery_resume_router
from app.routes.recovery_transition import router as recovery_transition_router
from app.routes.multi_model import router as multi_model_router
from app.routes.system_prompt import router as system_prompt_router


ROUTERS = [
    (builder_router, ["Builder"]), (code_router, ["Code"]), (execute_router, ["Execute"]),
    (validate_router, ["Validate"]), (memory_router, ["Memory"]), (memory_links_router, ["Memory Links"]), (health_router, None),
    (resources_router, None), (brain_router, ["Brain"]), (run_router, ["Run"]),
    (project_insights_router, ["Project Insights"]), (projects_router, ["Projects"]),
    (project_details_router, ["Project Details"]), (continue_router, ["Continue"]),
    (compare_router, ["Compare"]), (project_versions_router, ["Project Versions"]),
    (project_files_router, ["Project Files"]), (project_file_content_router, ["Project File Content"]),
    (search_router, ["Search"]), (text_ideas_router, ["Idea Capture"]), (idea_planning_router, ["Idea Planning"]), (voice_capture_router, ["Voice Capture"]), (voice_history_router, ["Voice History"]), (artifacts_router, ["Artifacts"]),
    (command_router, ["Command"]), (session_insights_router, ["Session Insights"]), (sessions_router, ["Sessions"]),
    (goals_router, ["Goals"]), (goal_intelligence_router, ["Goal Intelligence"]), (agents_router, ["Agents"]),
    (workflow_insights_router, ["Workflow Insights"]), (workflows_router, ["Workflows"]),
    (auth_router, ["Authentication"]), (devices_router, ["Device Gateway"]), (device_profiles_router, ["Device Profiles"]), (ai_modes_router, ["AI Modes"]), (personal_preferences_router, ["Personal Preferences"]),
    (system_prompt_router, ["System Prompt"]),
    (project_terminal_router, ["Project Terminal"]), (project_preview_router, ["Project Preview"]),
    (web_router, ["Web Access"]), (recovery_router, ["Workflow Recovery"]), (features_router, ["Features"]),
    (intelligence_router, ["Intelligence and Modes"]), (notepad_router, ["Notepad"]),
    (image_understanding_router, ["Image Understanding"]), (image_generation_router, ["Image Generation"]),
    (research_library_router, ["Research Library"]), (research_compare_router, ["Research"]), (recovery_checkpoints_router, ["Recovery Checkpoints"]),
    (personal_context_router, ["Personal Context"]), (knowledge_router, None), (personal_library_router, ["Personal Library"]), (electronics_assistant_router, ["Electronics Assistant"]), (circuit_planning_router, ["Circuit Planning"]), (microcontroller_projects_router, ["Microcontroller Projects"]), (project_documentation_router, ["Project Documentation"]), (personal_todos_router, ["Personal To-Do"]), (system_status_router, None),
    (core_features_router, None), (core_runtime_router, None), (reminders_router, ["Reminders"]),
    (notifications_router, ["Notifications"]), (quick_tasks_router, ["Quick Tasks"]),
    (task_insights_router, ["Task Insights"]), (core_events_router, ["Core Events"]),
    (system_health_router, ["System Health"]), (core_diagnostics_router, ["Core Diagnostics"]),
    (goal_insights_router, ["Goal Insights"]), (next_actions_router, ["Next Actions"]),
    (personal_briefing_router, ["Personal Briefing"]), (decision_context_router, ["Memory Context"]),
    (decision_lifecycle_router, ["Decision Intelligence"]),
    (action_priority_router, ["Action Priority"]), (core_activity_summary_router, ["System Activity"]),
    (briefing_priorities_router, None), (core_attention_router, None), (execution_loop_router, None),
    (blocker_queue_router, None), (blocker_insights_router, None), (execution_readiness_router, None),
    (core_intelligence_router, ['Core Intelligence']), (action_summary_router, ['Action Summary']),
    (execution_feedback_router, ['Execution Feedback']), (outcome_insights_router, ['Outcome Insights']),
    (execution_review_router, ['Execution Review']),
    (outcome_learning_router, ['Outcome Learning']),
    (learning_loop_router, ['Learning Loop']),
    (recovery_intelligence_router, ['Recovery Intelligence']),
    (workflow_recovery_router, ['Workflow Recovery']),
    (task_recovery_router, ['Task Recovery']),
    (task_recovery_plan_router, ['Task Recovery Plan']),
    (recovery_resume_router, ['Recovery Resume']),
    (recovery_transition_router, ['Recovery Transition']),
    (multi_model_router, ["Multi-Model Intelligence"]),
]


def register_routes(app):
    """Attach every configured Lumira API router exactly once.

    Router identity is checked before registration so an accidental duplicate in
    this central registry cannot silently expose the same router twice.
    """
    seen_router_ids: set[int] = set()
    for router, tags in ROUTERS:
        router_id = id(router)
        if router_id in seen_router_ids:
            raise RuntimeError("Duplicate router registered in Lumira router registry")
        seen_router_ids.add(router_id)
        if tags is None:
            app.include_router(router)
        else:
            app.include_router(router, tags=tags)
