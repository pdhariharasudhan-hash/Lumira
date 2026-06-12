# Lumira Architecture

## Mission

Lumira is a modular AI Operating System designed to:

* Understand goals
* Plan execution
* Generate projects
* Store memory
* Manage workspaces
* Track history
* Execute workflows

---

# Core Layers

## Planner Layer

Purpose:
Convert goals into executable plans.

Services:

* GoalDecomposer
* PlanRegistry
* PlannerService
* PlanExecutor
* PlanExecutorV2
* PlanExecutorV3

Flow:

Goal
→ Intent
→ Plan
→ Execution

---

## Builder Layer

Purpose:
Transform ideas into implementation steps.

Services:

* BuilderService
* ProjectClassifier

Output:

* Objective
* Suggested Steps
* Scope
* Priority

---

## Execution Layer

Purpose:
Determine execution order.

Services:

* ExecuteService
* ExecutionSessionService

Output:

* Task Order
* Current Task
* Expected Output

---

## Code Generation Layer

Purpose:
Generate project code.

Services:

* CodeService
* FeatureDetector
* FieldInference
* TemplateEngine

Output:

* main.py
* requirements.txt
* Generated Project

---

## Memory Layer

Purpose:
Store long-term system data.

Services:

* MemoryService

Stores:

* Memory
* State
* Configuration

---

## Workspace Layer

Purpose:
Organize projects.

Services:

* WorkspaceService
* SnapshotService
* ArtifactCollectionService

Handles:

* Workspaces
* Snapshots
* Collections

---

## History Layer

Purpose:
Track events.

Services:

* EventLoggerService
* ActivityFeedService
* PlannerHistoryService

Tracks:

* Plans
* Events
* Activity

---

## Dashboard Layer

Purpose:
Provide system overview.

Services:

* DashboardService

Displays:

* Recent Events
* Recent Plans
* Active Workspace
* Metrics

---

# Current Status

Foundation Complete

Next Major Milestone:

Agent Architecture
