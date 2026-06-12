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

        return self.plans.get(
            plan_name
        )

    def list_plans(
        self
    ):

        return list(
            self.plans.keys()
        )