# Workflow Step Mapping

## Purpose

Map planner steps to execution handlers.

---

validate

Handler:
Validation Service

Purpose:
Verify goal and inputs.

---

builder

Handler:
Builder Service

Purpose:
Create execution blueprint.

---

execute

Handler:
Execute Service

Purpose:
Create execution order.

---

code

Handler:
CodeAgent

Purpose:
Generate code artifacts.

---

save_project

Handler:
Workspace Service

Purpose:
Store generated project.

---

Future Steps

research
→ ResearchAgent

memory
→ Memory Service

voice
→ VoiceAgent

vision
→ VisionAgent

automation
→ AutomationAgent

---

Architecture

Goal
↓
PlannerAgent

returns

[
validate,
builder,
execute,
code,
save_project
]

↓

WorkflowEngine

maps step
↓
handler

executes handler
↓
collects result
