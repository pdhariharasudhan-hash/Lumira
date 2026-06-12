class LanguageDetectionService:

    def detect(
        self,
        text: str
    ):

        if not text:

            return {

                "language":
                "unknown",

                "confidence":
                0.0
            }

        tamil_found = False
        english_found = False

        for char in text:

            # Tamil Unicode Block
            if "\u0B80" <= char <= "\u0BFF":

                tamil_found = True

            elif (
                char.isascii()
                and char.isalpha()
            ):

                english_found = True

        # -------------------------
        # MIXED LANGUAGE
        # -------------------------

        if (
            tamil_found
            and
            english_found
        ):

            return {

                "language":
                "ta-en",

                "confidence":
                1.0
            }

        # -------------------------
        # TAMIL ONLY
        # -------------------------

        if tamil_found:

            return {

                "language":
                "ta",

                "confidence":
                1.0
            }

        # -------------------------
        # ENGLISH ONLY
        # -------------------------

        if english_found:

            return {

                "language":
                "en",

                "confidence":
                1.0
            }

        return {

            "language":
            "unknown",

            "confidence":
            0.0
        }