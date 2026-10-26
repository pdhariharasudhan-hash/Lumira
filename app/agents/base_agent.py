class BaseAgent:

    def __init__(
        self,
        name: str,
        description: str,
        capabilities=None
    ):

        self.name = name

        self.description = (
            description
        )

        self.capabilities = (
            capabilities
            or
            []
        )

    def execute(
        self,
        task: str
    ):

        raise NotImplementedError(

            f"{self.name} "
            "must implement execute()"
        )

    def status(
        self
    ):

        return {

            "name":
            self.name,

            "description":
            self.description,

            "capabilities":
            self.capabilities,

            "status":
            "ready"
        }