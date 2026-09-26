class IntentClassifierService:

    def classify(
        self,
        command: str
    ):

        command = command.lower()

        if "enter " in command and " mode" in command:
            return "mode"

        if command.startswith("build"):
            return "build"

        if command.startswith("add "):
            return "continue"

        if command.startswith("search"):
            return "search"

        if command.startswith("continue"):
            return "continue"

        if command.startswith("show"):
            return "show"

        return "chat"