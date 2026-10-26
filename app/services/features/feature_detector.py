class FeatureDetector:

    def detect(
        self,
        idea: str
    ):

        lower = idea.lower()

        features = []


        if (
            "search"
            in lower
        ):

            features.append(
                "search"
            )


        if (
            "authentication"
            in lower
            or
            "login"
            in lower
            or
            "auth"
            in lower
        ):

            features.append(
                "auth"
            )


        if (
            "sqlite"
            in lower
        ):

            features.append(
                "sqlite"
            )


        if (
            "pagination"
            in lower
        ):

            features.append(
                "pagination"
            )


        if (

            "csv"
            in lower

            or

            "export"
            in lower

        ):

            features.append(
                "export_csv"
            )


        if (
            "analytics"
            in lower
        ):

            features.append(
                "analytics"
            )


        if (
            "sorting"
            in lower
            or
            "sort"
            in lower
        ):

            features.append(
                "sorting"
            )


        return features