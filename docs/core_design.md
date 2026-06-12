# Lumira Core Design

## Purpose

LumiraCore is the central orchestrator of the Lumira Operating System.

It does not perform planning, execution, memory management, or code generation itself.

Instead, it coordinates services.

---

## Responsibilities

### Service Access

Access all registered services through ServiceRegistry.

Examples:

* PlannerService
* BuilderService
* ExecuteService
* CodeService
* MemoryService
* WorkspaceService
* DashboardService

---

### Goal Processing

Accept a user goal.

Example:

build expense tracker api

Route the goal through the correct workflow.

---

### Workflow Coordination

Manage execution flow:

Goal
→ Planner
→ Builder
→ Execute
→ Code
→ Memory
→ History

---

### Session Creation

Create execution sessions.

Track:

* Goal
* Timestamp
* Outputs
* Status

---

### Event Logging

Record major actions.

Examples:

* plan_created
* project_generated
* workspace_created

---

## Non Responsibilities

LumiraCore must NOT:

* Generate code
* Build APIs
* Store memory directly
* Manage files directly
* Implement business logic

Those responsibilities belong to services.

---

## Service Registry Responsibilities

ServiceRegistry owns service instances.

Examples:

PlannerService
BuilderService
ExecuteService
CodeService
MemoryService
WorkspaceService
DashboardService

---

## Future Expansion

Future services:

* AgentManager
* VoiceManager
* VisionManager
* ToolManager
* TaskManager

These will also be registered through ServiceRegistry.

---

## Architecture Goal

User Goal
↓
LumiraCore
↓
ServiceRegistry
↓
Services
↓
Results

LumiraCore becomes the kernel of Lumira.
