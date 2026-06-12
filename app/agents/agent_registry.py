class AgentRegistry:

    def __init__(
        self
    ):

        self.agents = {}

    def register(
        self,
        agent
    ):

        self.agents[
            agent.name
        ] = agent

    def get(
        self,
        name: str
    ):

        return self.agents.get(
            name
        )

    def exists(
        self,
        name: str
    ):

        return (
            name
            in
            self.agents
        )

    def list_agents(
        self
    ):

        return list(
            self.agents.keys()
        )

    def count(
        self
    ):

        return len(
            self.agents
        )