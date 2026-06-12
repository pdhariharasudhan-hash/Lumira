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

    def dispatch(
        self,
        task: str
    ):

        task_lower = (
            task.lower()
        )

        code_keywords = [

            "build",
            "create",
            "generate",
            "code",
            "api",
            "app",
            "website"
        ]

        research_keywords = [

            "research",
            "find",
            "analyze",
            "investigate",
            "learn",
            "explain"
        ]

        for keyword in code_keywords:

            if keyword in task_lower:

                return self.run(

                    "code_agent",
                    task
                )

        for keyword in research_keywords:

            if keyword in task_lower:

                return self.run(

                    "research_agent",
                    task
                )

        return self.run(

            "research_agent",
            task
        )

    def list_agents(
        self
    ):

        return (
            self.registry
            .list_agents()
        )