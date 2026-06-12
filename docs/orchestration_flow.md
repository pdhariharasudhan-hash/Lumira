# Lumira Orchestration Flow

## Primary Workflow

User Goal
↓
LumiraCore.run()
↓
PlannerService
↓
BuilderService
↓
ExecuteService
↓
CodeService
↓
MemoryService
↓
History Services
↓
Return Result

---

## Planning Workflow

LumiraCore.plan()
↓
PlannerService
↓
Return Plan

---

## Build Workflow

LumiraCore.build()
↓
BuilderService
↓
Return Build Plan

---

## Execution Workflow

LumiraCore.execute()
↓
ExecuteService
↓
Return Execution Plan

---

## Code Workflow

LumiraCore.generate()
↓
CodeService
↓
Return Files

---

## Future Agent Workflow

User Goal
↓
LumiraCore
↓
AgentManager
↓
Selected Agent
↓
Planner
↓
Builder
↓
Execute
↓
Code

---

## Rule

LumiraCore never contains implementation logic.

LumiraCore only orchestrates services.
