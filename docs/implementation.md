## Current Docker-free mode

Docker invocations have been removed from the project test runner and diagnostics. DevOps focuses on local dependency/build/runtime configuration and instructions, with approved file changes. Agent instructions disallow container setup. The UI reports manual project verification. No arbitrary host shell fallback was added. QA execution remains blocked pending actual verification; no manual-result import/approval UI exists yet. Existing project files and history are preserved, and old task descriptions are not rewritten. Restart the backend to activate the changed policies.

# Implementation notes

The browser state is a projection of persisted backend records. It never fabricates tasks, tool results, or progress.

## Run lifecycle

pending → queued → running → awaiting_approval → running → completed

A run can also end failed, blocked, cancelled, or interrupted. Approval waits expire after 15 minutes. Provider generation is bounded to 360 seconds, test execution to 120 seconds, and task retries to 3 attempts. The sequential workflow stops after 24 iterations.

Planner output is validated before a plan approval is created. Task keys must be unique, dependencies must refer to earlier entries, and the plan must include QA and review.

Code proposals contain complete file replacements. Paths and role permissions are validated; each approval carries the exact diff, proposed content, and source hash. All source hashes are checked again before writes. Rejected, expired, or stale approvals never authorize replacement writes.

The application owns file access and test execution. Codex runs in a separate scratch workspace with native tools disabled, a deny hook, and a restricted permission profile. A failure to create that secure runtime aborts the run; there is no fallback to full access.

## QA feedback

When a sequential workflow receives a real nonzero test result with at least one executed test, it creates a repair task for the most recent developer. QA then depends on that repair. Two repair cycles are possible before the QA attempt limit is reached. In the current Docker-free mode, project tests return executed=false and pause the workflow for manual verification; they never trigger automatic repair.

## Persistence and recovery

SQLite uses WAL mode. Entity updates and their associated event share one SQLAlchemy transaction. The generic records table stores projects, tasks, runs, and approvals; domain validation lives in Pydantic models and orchestrator rules.

WebSocket consumers request events after a cursor and refresh materialized state. On restart, active task/run records become interrupted and pending approvals expire. Work is never silently re-executed.

There is one backend process and one live execution at a time. Multi-process coordination is outside this version.

## Interface boundaries

- REST: session bootstrap, state, projects, planning, workflow, task run/cancel, approvals, account/login, diagnostics.
- WebSocket: persisted event batches and heartbeats.
- Provider protocol: structured generation with a schema and runtime event callback.
- Source tools: bounded file index/read, approved replacement writes, manual project test verification (Docker disabled).
- Game: scene composition and A* navigation consume application state; animation never changes backend state.

## Validation

29 backend tests passed; one symbolic-link test was skipped because this Windows host does not permit creating symlinks. They cover protected paths, nested source selection, persistent event replay, plan cycles, approval gates/rejection/replay, stale file hashes, cancellation, QA evidence, role restrictions, restart recovery, dependencies, bounded QA feedback, retry limits, HTTP session/origin controls, project creation, and WebSocket delivery.

The fake provider and fake test results used by contract tests exist only in the tests package.

Production TypeScript compilation and Vite build passed. The 3D office and navigation surfaces were inspected in the in-app browser.

A real account read returned ChatGPT authentication with the Plus plan. Full inference and real Docker execution remain unverified because the environment refused access to Windows sandbox provisioning and the Docker named pipe.

The WebGL scene now uses a detailed reference-driven 2.5D environment plate, six distinct character identities, normalized walking sprites, idle roaming, and state-driven task return. See office-art.md for the visual update and 92 office checks. The full requested sprite animation set, depth of field, arbitrary package-dependent test runners, parallel execution, and Ollama are still future work.

## Project lifecycle controls

Project deletion checks the exact name and stored workspace path, refuses active runs/workflows and unsafe or overlapping directories, removes the entire dedicated workspace, then transactionally removes project tasks, runs and approvals. A project.deleted audit event remains. Failed folder deletion keeps the project record and reports possible partial removal. Open folder uses the stored absolute path with Windows File Explorer; a full selectable path and Copy path are also provided. The route handlers are covered through authenticated HTTP tests with disposable workspaces.
