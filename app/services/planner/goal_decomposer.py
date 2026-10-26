class GoalDecomposer:

    def decompose(
        self,
        goal: str
    ):

        goal = (
            goal.lower()
            .strip()
        )

        if (
            "api" in goal
            or
            "backend" in goal
        ):

            return {

                "intent":
                "build_api",

                "goal":
                goal
            }

        if (
            "image" in goal
            or
            "generate image" in goal
        ):

            return {

                "intent":
                "generate_image",

                "goal":
                goal
            }

        if (
            "voice" in goal
            or
            "audio" in goal
        ):

            return {

                "intent":
                "voice_capture",

                "goal":
                goal
            }

        return {

            "intent":
            "search",

            "goal":
            goal
        }