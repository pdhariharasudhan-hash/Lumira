# Lumira Agent Architecture

## Purpose

Agents are specialized workers that perform tasks through LumiraCore.

Agents do not directly communicate with each other.

All coordination happens through AgentManager.

---

# BaseAgent

Responsibilities:

* Name
* Description
* Capabilities
* Execute Task

Methods:

execute(task)

status()

---

# Agent Registry

Responsibilities:

* Register Agents
* Remove Agents
* List Agents
* Retrieve Agents

Methods:

register(agent)

get(name)

list_agents()

---

# Agent Manager

Responsibilities:

* Receive Tasks
* Select Agent
* Execute Agent
* Return Results

Methods:

run(agent_name, task)

dispatch(task)

---

# Initial Agents

ResearchAgent

Purpose:
Gather information.

---

CodeAgent

Purpose:
Generate code.

---

PlannerAgent

Purpose:
Create plans.

---

WorkspaceAgent

Purpose:
Manage workspaces.

---

# Future Agents

VoiceAgent

VisionAgent

AutomationAgent

MemoryAgent

ToolAgent

---

# Architecture

User
↓
LumiraCore
↓
AgentManager
↓
AgentRegistry
↓
Agent

Agent
↓
Services

Planner
Builder
Execute
Code
Memory
Workspace

---

# Rule

Agents never directly access other agents.

All coordination flows through AgentManager.
