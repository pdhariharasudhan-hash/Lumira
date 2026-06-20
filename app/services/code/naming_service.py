class NamingService:

    def pluralize(
        self,
        word: str
    ) -> str:

        word = (
            word
            .strip()
            .lower()
        )

        if word.endswith(
            "y"
        ) and len(word) > 1:

            previous = (
                word[-2]
            )

            if previous not in [

                "a",
                "e",
                "i",
                "o",
                "u"
            ]:

                return (
                    word[:-1]
                    + "ies"
                )

        if word.endswith(
            (
                "s",
                "x",
                "z",
                "ch",
                "sh"
            )
        ):

            return (
                word
                + "es"
            )

        return (
            word
            + "s"
        )

    def singularize(
        self,
        word: str
    ) -> str:

        word = (
            word
            .strip()
            .lower()
        )

        if word.endswith(
            "ies"
        ):

            return (
                word[:-3]
                + "y"
            )

        if word.endswith(
            "es"
        ):

            endings = [

                "ses",
                "xes",
                "zes",
                "ches",
                "shes"
            ]

            for ending in endings:

                if word.endswith(
                    ending
                ):

                    return (
                        word[:-2]
                    )

        if word.endswith(
            "s"
        ) and len(word) > 1:

            return (
                word[:-1]
            )

        return word
        