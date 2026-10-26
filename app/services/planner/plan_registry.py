class PlanRegistry:

    def __init__(self):

        self.plans = {

            "build_api": [
                "validate",
                "builder",
                "execute",
                "code",
                "save_project"
            ],

            "generate_image": [
                "generate_image",
                "save_artifact"
            ],

            "voice_capture": [
                "capture_audio",
                "save_artifact",
                "transcribe",
                "summarize"
            ],

            "search": [
                "search"
            ]
        }

    def get_plan(
        self,
        plan_name: str
    ):
        """Return an isolated copy so callers cannot mutate registered plans."""
        if not isinstance(plan_name, str):
            return None
        plan = self.plans.get(plan_name)
        return list(plan) if isinstance(plan, list) else None

    def list_plans(
        self
    ):

        return list(
            self.plans.keys()
        )