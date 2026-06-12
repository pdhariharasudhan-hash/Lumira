from app.agents.agent_registry import (
    AgentRegistry
)


class AgentManager:

    def __init__(
        self
    ):

        self.registry = (
            AgentRegistry()
        )

    def register(
        self,
        agent
    ):

        self.registry.register(
            agent
        )

    def run(
        self,
        agent_name: str,
        task: str
    ):

        agent = (
            self.registry.get(
                agent_name
            )
        )

        if not agent:

            return {

                "success":
                False,

                "message":
                "agent not found"
            }

        result = (
            agent.execute(
                task
            )
        )

        return {

            "success":
            True,

            "agent":
            agent_name,

            "task":
            task,

            "result":
            result
        }

    def list_agents(
        self
    ):

        return (
            self.registry
            .list_agents()
        )