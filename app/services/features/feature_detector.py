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
            or "dashboard" in lower
            or "metrics" in lower
            or "statistics" in lower
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


        if any(term in lower for term in ("notification", "reminder", "alert")):
            features.append("notifications")

        if any(term in lower for term in ("upload", "attachment")):
            features.append("file_upload")

        if any(term in lower for term in ("voice", "microphone", "speech")):
            features.append("voice_support")

        if any(term in lower for term in ("api", "endpoint")):
            features.append("api")

        return list(dict.fromkeys(features))