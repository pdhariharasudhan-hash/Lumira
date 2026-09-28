"""
Deterministic Operations capability service.
"""

from typing import Any, Dict


class OperationsCapabilityService:

    def business_operations(self, request, session_id=None, project_id=None, goal_id=None):
        return self._tracked_workflow(
            "business_operations", request, session_id, project_id, goal_id,
            ["Define today's operational objective and scope.",
             "Identify prerequisites, dependencies, and blockers.",
             "Perform the supported local work and record its result.",
             "Verify the outcome and update task status."],
        )

    def workflow_automation(self, request, session_id=None, project_id=None, goal_id=None):
        return self._tracked_workflow(
            "workflow_automation", request, session_id, project_id, goal_id,
            ["Define the workflow objective and trigger.",
             "List the registered actions and their required inputs.",
             "Order actions by prerequisites and identify failure states.",
             "Run only supported local capabilities; external actions remain pending.",
             "Verify results and record completion or blockers."],
        )

    def scheduled_tasks(self, request):
        return self._result("scheduled_tasks", request, "scheduled task",
            ["define task", "define schedule", "define execution conditions",
             "define result handling", "verify schedule"])

    def monitoring(self, request):
        return self._result("monitoring", request, "monitoring",
            ["define target", "define monitored conditions", "define thresholds",
             "define response action", "define verification"])

    def process_optimization(self, request):
        return self._result("process_optimization", request, "process optimization",
            ["define process", "measure baseline", "identify bottlenecks",
             "identify improvements", "measure result", "repeat validated improvements"])

    def file_automation(self, request):
        return self._result("file_automation", request, "file automation",
            ["define file operation", "identify source", "define transformation",
             "define destination", "verify output"])

    def email_automation(self, request):
        return self._result("email_automation", request, "email automation",
            ["define email workflow", "identify trigger", "define message requirements",
             "define recipient rules", "verify delivery conditions"])

    def system_monitoring(self, request):
        return self._result("system_monitoring", request, "system monitoring",
            ["define system target", "identify metrics", "define thresholds",
             "detect abnormal conditions", "define response", "verify system state"])

    def business_process_management(self, request):
        return self._result("business_process_management", request, "business process management",
            ["define process", "identify owners", "map process stages",
             "identify dependencies", "define metrics", "verify process"])

    def recurring_jobs(self, request):
        return self._result("recurring_jobs", request, "recurring job",
            ["define recurring task", "define interval", "define execution conditions",
             "define failure handling", "verify recurrence"])

    def operational_dashboards(self, request):
        return self._result("operational_dashboards", request, "operational dashboard",
            ["define operational metrics", "identify data sources",
             "define dashboard views", "define update frequency", "verify metrics"])

    def automated_reports(self, request):
        return self._result("automated_reports", request, "automated report",
            ["define report objective", "identify data sources", "define report structure",
             "define generation schedule", "verify report output"])

    @staticmethod
    def _result(capability, request, objective, steps):
        return {
            "success": True,
            "capability": capability,
            "request": request.strip() if isinstance(request, str) else "",
            "objective": objective,
            "steps": list(steps),
            "status": "planned",
            "execution_started": False,
            "execution_boundary": "This capability created a local plan; no schedule, monitoring, file, email, or external action was executed.",
        }

    def _tracked_workflow(self, capability, request, session_id, project_id, goal_id, tasks):
        if not isinstance(request, str) or not request.strip() or len(request) > 10_000:
            return {"success": False, "status": "rejected", "code": "invalid_request", "message": "Operational requests must contain 1 to 10000 characters."}
        from app.services.artifacts.artifact_manager_service import ArtifactManagerService
        from app.services.memory.memory_service import MemoryService
        from app.services.work_items.work_item_service import WorkItemService
        import json

        memory = MemoryService()
        try:
            goal = memory.update_goal(
                goal_id,
                title=request.strip()[:200],
                objective="Complete and verify the requested operational workflow.",
                project_id=project_id,
                status="active",
            ) if goal_id else None
        except KeyError:
            goal = None
        if goal is None:
            goal = memory.create_goal(
                title=request.strip()[:200],
                objective="Complete and verify the requested operational workflow.",
                priority="high",
                project_id=project_id,
            )
        workflow = WorkItemService().create_workflow(
            "operations", capability.replace("_", " ").title(), request.strip(), tasks,
            session_id=session_id, project_id=project_id, goal_id=goal["goal_id"],
        )
        plan = {
            "type": "operations_workflow",
            "capability": capability,
            "request": request.strip(),
            "goal_id": goal["goal_id"],
            "workflow_id": workflow["workflow_id"],
            "tasks": workflow["tasks"],
            "execution_boundary": "Only registered local actions execute; external actions require a configured provider.",
            "status": "planned",
        }
        try:
            artifact = ArtifactManagerService().create_artifact(
                "exports", json.dumps(plan, ensure_ascii=False), capability, "json"
            )
            memory.update_goal(goal["goal_id"], artifact_ids=[artifact["artifact_id"]])
        except Exception:
            return {
                "success": False,
                "status": "failed",
                "code": "artifact_storage_failed",
                "message": "The workflow tasks were recorded, but the operational artifact could not be stored.",
                "goal_id": goal["goal_id"],
                "workflow_id": workflow["workflow_id"],
            }
        return {
            "success": True,
            "status": "planned",
            "capability": capability,
            "plan": plan,
            "goal": goal,
            "workflow": workflow,
            "artifact": artifact,
        }
