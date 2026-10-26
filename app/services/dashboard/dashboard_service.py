from app.services.history.activity_feed_service import (
    ActivityFeedService
)

from app.services.planner.planner_history_service import (
    PlannerHistoryService
)

from app.services.workspace.workspace_service import (
    WorkspaceService
)


class DashboardService:

    def get_dashboard(
        self
    ):

        events = (
            ActivityFeedService()
            .get_feed()
        )

        plans = (
            PlannerHistoryService()
            .get_history()
        )

        workspace = (
            WorkspaceService()
            .get_active_workspace()
        )

        return {

            "recent_events":
            events[-10:],

            "recent_plans":
            plans[-10:],

            "active_workspace":
            workspace,

            "event_count":
            len(
                events
            ),

            "plan_count":
            len(
                plans
            )
        }