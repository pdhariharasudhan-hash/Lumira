class CommandParserService:

    def parse(
        self,
        text: str
    ):

        text = (
            text
            .strip()
            .lower()
        )

        # ------------------
        # IMAGE GENERATION
        # ------------------

        if (
            "generate image"
            in text
        ):

            prompt = (
                text
                .replace(
                    "generate image",
                    ""
                )
                .strip()
            )

            return {

                "success":
                True,

                "capability":
                "generate_image",

                "payload": {

                    "prompt":
                    prompt,

                    "image_type":
                    "image"
                }
            }

        # ------------------
        # SEARCH
        # ------------------

        if (
            text.startswith(
                "search "
            )
        ):

            query = (
                text.replace(
                    "search",
                    "",
                    1
                )
                .strip()
            )

            return {

                "success":
                True,

                "capability":
                "search",

                "payload": {

                    "query":
                    query
                }
            }

        # ------------------
        # FEATURES
        # ------------------

        if (
            text.startswith(
                "activate "
            )
        ):

            feature = (
                text.replace(
                    "activate",
                    "",
                    1
                )
                .strip()
            )

            return {

                "success":
                True,

                "capability":
                "activate_feature",

                "payload": {

                    "feature":
                    feature
                }
            }

        if (
            text.startswith(
                "disable "
            )
        ):

            feature = (
                text.replace(
                    "disable",
                    "",
                    1
                )
                .strip()
            )

            return {

                "success":
                True,

                "capability":
                "deactivate_feature",

                "payload": {

                    "feature":
                    feature
                }
            }

        if (
            text == "list features"
        ):

            return {

                "success":
                True,

                "capability":
                "list_features",

                "payload":
                {}
            }

        return {

            "success":
            False,

            "message":
            "Unknown command"
        }