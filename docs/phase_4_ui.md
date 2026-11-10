# Phase 4 — Dashboard, Workspace and Agent UI

**Implementation status:** Complete for the roadmap's Phase 4 feature list.
**Release status:** Packaged-app visual acceptance remains open.

## Delivered

- Added a Dashboard navigation page with a read-only overview of core health, project/version counts, goals, workflows, sessions, registered agents, and artifact counts.
- Kept the existing Projects, Artifacts, Memory, Goals, Planner, Operations, Observability, Feature Control, Image Analysis, and Generator pages as the workspace UI.
- Added a dedicated Agents page that lists the agents actually returned by the backend and supports explicit task dispatch with automatic or selected-agent routing.
- Added dedicated Background Tasks and Self-Improvement pages to expose the Phase 5 controls and diagnostics.
- Added API client methods for agent discovery/dispatch, background task submission/list/detail, and learning-loop diagnostics.
- Fixed the agent dispatch request contract so an explicitly selected agent is accepted by the dispatch API rather than rejected as an unexpected field.
- The agent page does not silently delegate ordinary chat. Dispatch still goes through BrainAgentOrchestrator; capacity remains one agent at a time on this device.

## Verification

- MainLayout desktop UI suite: **26 passed**. Coverage includes dashboard navigation, registered-agent display and dispatch, background queue submission, and read-only learning diagnostics.
- Backend agent/workflow integration regression group: included in the Phase 5 focused verification report.
- Full desktop suite, lint and production build are tracked separately as final acceptance evidence.

## Remaining acceptance

- Visual inspection in the installed/packaged Windows application is not complete.
- Installer packaging and upgrade/data-preservation checks are not complete.
- Real provider-backed agent execution is not proven by UI mocks.


## Final verification update — 2026-11-06

- Full desktop Vitest suite: **38 passed across 5 test files**.
- Desktop lint: **0 warnings, 0 errors**.
- TypeScript/Vite production build: passed; generated bundle is approximately 416 KB JavaScript before gzip.
- Focused UI coverage includes dashboard, agent discovery/dispatch, background task submission, and learning diagnostics.
- Packaged Windows installer and visual acceptance were not attempted because free RAM remained below the 2 GB packaging threshold. Source build success is not packaged-app sign-off.
