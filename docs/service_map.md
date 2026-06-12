# Lumira Service Map

## Planner

PlannerService
├── GoalDecomposer
└── PlanRegistry

PlanExecutorV3
├── BuilderService
├── ExecuteService
└── CodeService

---

## Builder

BuilderService
└── ProjectClassifier

---

## Code Generation

CodeService
├── ProjectClassifier
├── FieldInference
├── FeatureDetector
└── TemplateEngine

---

## Execution

ExecuteService

ExecutionSessionService

---

## Workspace

WorkspaceService

ArtifactCollectionService

SnapshotService

---

## History

EventLoggerService

ActivityFeedService

PlannerHistoryService

---

## Dashboard

DashboardService
├── ActivityFeedService
├── PlannerHistoryService
└── WorkspaceService

---

## Current Bottlenecks

1. Services are directly instantiating other services.

Example:

PlanExecutorV3
→ BuilderService()
→ ExecuteService()
→ CodeService()

2. No dependency injection container.

3. No agent registry.

4. No central orchestration layer.

---

## Future Architecture

Goal
→ Agent Manager
→ Planner
→ Builder
→ Execute
→ Code
→ Memory
→ Workspace

Single orchestration layer controls all services.
