from __future__ import annotations
import asyncio
import difflib
import hashlib
import json
import uuid
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .agents import BASE, INSTRUCTIONS
from .security import safe_path, files, run_tests, devops_config_path, qa_artifact_path
from .store import Store, now
from .provider import Provider


def uid() -> str:
    return uuid.uuid4().hex[:16]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlannedTask(StrictModel):
    key: str
    agent_id: Literal["frontend", "backend", "qa", "reviewer", "devops"]
    title: str
    description: str
    acceptance_criteria: list[str]
    depends_on: list[str]


class Plan(StrictModel):
    summary: str
    tasks: list[PlannedTask] = Field(min_length=1, max_length=12)


class Change(StrictModel):
    path: str
    content: str = Field(max_length=200_000)


class Result(StrictModel):
    status: Literal["completed", "blocked"]
    summary: str
    findings: list[str]
    changes: list[Change] = Field(max_length=20)
    test_suite: Literal["none", "python", "node"]


def validate_plan(plan: Plan) -> None:
    seen: set[str] = set()
    for task in plan.tasks:
        if task.key in seen or not set(task.depends_on) <= seen:
            raise ValueError("Plan has duplicate keys, unknown dependencies or a cycle")
        seen.add(task.key)
    if not any(t.agent_id == "qa" for t in plan.tasks) or not any(
        t.agent_id == "reviewer" for t in plan.tasks
    ):
        raise ValueError("Plan must include QA and code review")


class Orchestrator:
    def __init__(self, store: Store, provider: Provider):
        self.store, self.provider = store, provider
        self.lock = asyncio.Lock()
        self.active: dict[str, asyncio.Task] = {}
        self.waiters: dict[str, asyncio.Future] = {}
        self.pipeline: asyncio.Task | None = None

    def start_workflow(self, project_id: str) -> None:
        if self.active or (self.pipeline and not self.pipeline.done()):
            raise ValueError("A run is already active")

        async def drive():
            self.store.emit(
                "workflow.started",
                project_id=project_id,
                message="Sequential workflow started",
            )
            try:
                for _ in range(24):
                    tasks = [
                        t
                        for t in self.store.all("tasks")
                        if t["project_id"] == project_id
                    ]
                    by_id = {t["id"]: t for t in tasks}
                    eligible = next(
                        (
                            t
                            for t in tasks
                            if t["status"] == "pending"
                            and all(
                                by_id[d]["status"] in {"completed", "skipped"}
                                for d in t["depends_on"]
                            )
                        ),
                        None,
                    )
                    if not eligible:
                        unfinished = [t for t in tasks if t["status"] not in {"completed", "skipped"}]
                        self.store.emit(
                            "workflow.paused" if unfinished else "workflow.completed",
                            project_id=project_id,
                            message="Resolve blocked tasks to continue"
                            if unfinished
                            else "Workflow finished; tasks completed or explicitly skipped",
                        )
                        return
                    self.queue(eligible, from_pipeline=True)
                    await self.active[eligible["id"]]
                    outcome = self.store.get("tasks", eligible["id"])
                    if outcome["status"] != "completed":
                        evidence = (outcome.get("result") or {}).get(
                            "test_result"
                        ) or {}
                        developers = [
                            t
                            for t in tasks
                            if t["agent_id"] in {"frontend", "backend"}
                            and t["status"] == "completed"
                        ]
                        if (
                            outcome["agent_id"] == "qa"
                            and evidence.get("test_count", 0) > 0
                            and evidence.get("exit_code", 0) != 0
                            and outcome["attempts"] < 3
                            and developers
                        ):
                            developer = developers[-1]
                            fix = {
                                "id": uid(),
                                "project_id": project_id,
                                "agent_id": developer["agent_id"],
                                "title": "Fix QA findings: " + outcome["title"],
                                "description": "Fix these verified test failures without weakening tests: "
                                + str(evidence.get("output", ""))[-12000:],
                                "acceptance_criteria": [
                                    "Previously failing sandbox tests pass"
                                ],
                                "depends_on": [developer["id"]],
                                "status": "pending",
                                "attempts": 0,
                                "created_at": now(),
                            }
                            self.store.save(
                                "tasks", fix, "qa.feedback", message=fix["title"]
                            )
                            outcome["depends_on"] = [*outcome["depends_on"], fix["id"]]
                            outcome["status"] = "pending"
                            self.store.save(
                                "tasks",
                                outcome,
                                "qa.retry_scheduled",
                                message="Retry QA after the repair task completes",
                            )
                            continue
                        self.store.emit(
                            "workflow.paused",
                            project_id=project_id,
                            message="Workflow paused: " + outcome["status"],
                        )
                        return
                self.store.emit(
                    "workflow.paused",
                    project_id=project_id,
                    message="Workflow iteration limit reached",
                )
            finally:
                self.pipeline = None

        self.pipeline = asyncio.create_task(drive())

    def recover(self) -> None:
        for task in self.store.all("tasks"):
            if task["status"] in {"running", "awaiting_approval", "queued"}:
                task["status"] = "interrupted"
                self.store.save(
                    "tasks",
                    task,
                    "task.interrupted",
                    message="Server restarted; retry explicitly.",
                )
        for run in self.store.all("runs"):
            if run["status"] in {"running", "queued", "awaiting_approval"}:
                run["status"] = "interrupted"
                self.store.save("runs", run, "run.interrupted")
        for a in self.store.all("approvals"):
            if a["status"] == "pending":
                a["status"] = "expired"
                self.store.save("approvals", a, "approval.expired")

    def queue(
        self, task: dict, *, from_pipeline: bool = False, manual_retry: bool = False
    ) -> None:
        if self.active or (
            self.pipeline and not self.pipeline.done() and not from_pipeline
        ):
            raise ValueError("Another run is active. Wait or cancel it first.")
        attempt = task.get("attempts", 0) + 1
        explicit_retry = manual_retry and not from_pipeline and task["status"] in {
            "failed", "blocked", "cancelled", "interrupted"
        }
        if attempt > 3 and not explicit_retry:
            raise ValueError("Automatic retry limit reached (3). Retry the task manually after resolving the issue.")
        task.pop("error", None)
        task["status"] = "queued"
        task["attempts"] = attempt
        task["run_id"] = uid()
        self.store.save("tasks", task, "task.queued")
        self.store.save(
            "runs",
            {
                "id": task["run_id"],
                "task_id": task["id"],
                "project_id": task["project_id"],
                "agent_id": task["agent_id"],
                "status": "queued",
                "started_at": now(),
                "attempt": task["attempts"],
            },
            "run.created",
        )
        self.active[task["id"]] = asyncio.create_task(self._run(task))

    async def approval(self, task: dict, kind: str, payload: dict) -> bool:
        a = {
            "id": uid(),
            "project_id": task["project_id"],
            "task_id": task["id"],
            "agent_id": task["agent_id"],
            "kind": kind,
            "payload": payload,
            "status": "pending",
            "created_at": now(),
        }
        future = asyncio.get_running_loop().create_future()
        self.waiters[a["id"]] = future
        task["status"] = "awaiting_approval"
        self.store.save("tasks", task, "task.awaiting_approval")
        self.store.save(
            "approvals",
            a,
            "approval.requested",
            message=f"Review {kind} before continuing",
        )
        try:
            return bool(await asyncio.wait_for(future, 900))
        finally:
            self.waiters.pop(a["id"], None)
            current = self.store.get("approvals", a["id"])
            if current["status"] == "pending":
                current["status"] = "expired"
                self.store.save("approvals", current, "approval.expired")

    def decide(self, id: str, approve: bool) -> None:
        a = self.store.get("approvals", id)
        future = self.waiters.get(id)
        if a["status"] != "pending" or not future or future.done():
            raise ValueError("Approval is no longer active")
        a["status"] = "approved" if approve else "rejected"
        a["decided_at"] = now()
        self.store.save("approvals", a, "approval.decided", message=a["status"])
        future.set_result(approve)

    def cancel(self, id: str) -> None:
        if id not in self.active:
            raise ValueError("Task is not running")
        self.active[id].cancel()

    def skip(self, id: str) -> dict:
        task = self.store.get("tasks", id)
        if self.active or (self.pipeline and not self.pipeline.done()):
            raise ValueError("Wait for the active run to finish or cancel it before skipping a task")
        if task["status"] not in {"pending", "failed", "blocked", "cancelled", "interrupted"}:
            raise ValueError("Task cannot be skipped in its current state")
        task["status"] = "skipped"
        task["skipped_at"] = now()
        self.store.save("tasks", task, "task.skipped", message="Skipped by user; task was not completed. Dependencies may proceed.")
        return task

    async def _run(self, task: dict) -> None:
        try:
            async with self.lock:
                task["status"] = "running"
                self.store.save("tasks", task, "agent.thinking", message=task["title"])
                project = self.store.get("projects", task["project_id"])
                root = Path(project["workspace"]).resolve()

                def emit(event: str, **data: object) -> None:
                    self.store.emit(
                        event,
                        project_id=project["id"],
                        task_id=task["id"],
                        run_id=task["run_id"],
                        agent_id=task["agent_id"],
                        **data,
                    )

                names = files(root)
                snapshot: dict[str, str] = {}
                total = 0
                for name in names:
                    p = safe_path(root, name)
                    content = p.read_text(encoding="utf-8", errors="replace")
                    if total + len(content) > 100_000:
                        continue
                    total += len(content)
                    snapshot[name] = content
                emit(
                    "tool.completed",
                    tool="workspace.read",
                    message=f"Read {len(snapshot)} source files",
                    files=list(snapshot),
                )
                context = {
                    "requirement": project["requirement"],
                    "task": {
                        k: v for k, v in task.items() if k not in {"result", "error"}
                    },
                    "file_index": names,
                    "planning_history": [
                        {"request": t["description"], "status": t["status"], "plan": t.get("result")}
                        for t in self.store.all("tasks")
                        if t["project_id"] == project["id"] and t["agent_id"] == "planner" and t["id"] != task["id"]
                    ] if task["agent_id"] == "planner" else [],
                    "skipped_tasks": [
                        {"id": t["id"], "title": t["title"], "status": "skipped"}
                        for t in self.store.all("tasks")
                        if t["project_id"] == project["id"] and t["status"] == "skipped"
                    ],
                    "source_files": snapshot,
                    "previous_results": [
                        {
                            "title": t["title"],
                            "result": {
                                k: v
                                for k, v in (t.get("result") or {}).items()
                                if k not in {"changes", "tasks"}
                            },
                        }
                        for t in self.store.all("tasks")
                        if t["project_id"] == project["id"]
                        and t["status"] == "completed"
                    ],
                }
                planner = task["agent_id"] == "planner"
                instructions = (
                    BASE.replace(
                        "Use ONLY the supplied office_* tools for workspace operations.",
                        "You receive a bounded source snapshot. Propose full replacement file contents in changes; the application applies approved changes. Do not invoke tools.",
                    )
                    + "\n"
                    + INSTRUCTIONS[task["agent_id"]]
                )
                if planner and task.get("planning_mode") == "follow_up":
                    instructions += (
                        "\nThis is a follow-up request for the existing project. Focus on the latest task description. "
                        "Use the current source snapshot, planning history and previous results. "
                        "Propose only the incremental changes needed; do not recreate completed work or restart the original project. "
                        "The new plan will be appended to existing tasks after user approval."
                    )
                raw = await asyncio.wait_for(
                    self.provider.generate(
                        instructions,
                        json.dumps(context, ensure_ascii=False),
                        Plan.model_json_schema()
                        if planner
                        else Result.model_json_schema(),
                        emit,
                    ),
                    360,
                )
                if planner:
                    plan = Plan.model_validate(raw)
                    validate_plan(plan)
                    if not await self.approval(task, "plan", plan.model_dump()):
                        raise ValueError("Plan rejected")
                    ids = {t.key: uid() for t in plan.tasks}
                    for entry in plan.tasks:
                        child = {
                            **entry.model_dump(),
                            "id": ids[entry.key],
                            "project_id": project["id"],
                            "status": "pending",
                            "attempts": 0,
                            "depends_on": [ids[k] for k in entry.depends_on],
                            "created_at": now(),
                        }
                        self.store.save(
                            "tasks", child, "task.created", message=child["title"]
                        )
                    task["result"] = plan.model_dump()
                else:
                    result = Result.model_validate(raw)
                    if (
                        task["agent_id"] not in {"frontend", "backend", "qa", "devops"}
                        and result.changes
                    ):
                        raise ValueError("This role is not allowed to change source")
                    if task["agent_id"] == "qa":
                        unsupported = [c.path for c in result.changes if not qa_artifact_path(c.path)]
                        if unsupported:
                            raise ValueError(
                                "QA cannot change these files: " + ", ".join(unsupported)
                                + ". Allowed: test files and QA documents (QA.md, TESTING.md, "
                                "test-plan.md, test-results.md, qa-report.md). "
                                "Assign application changes to Frontend/Backend."
                            )
                    if task["agent_id"] == "devops":
                        unsupported = [c.path for c in result.changes if not devops_config_path(c.path)]
                        if unsupported:
                            raise ValueError(
                                "DevOps cannot change these files: " + ", ".join(unsupported)
                                + ". Allowed: local build configuration, entry HTML, scripts and documentation. "
                                "Assign application components to Frontend/Backend. Docker files remain disabled."
                            )
                    proposals = []
                    if len({c.path for c in result.changes}) != len(result.changes):
                        raise ValueError("Duplicate change paths")
                    for change in result.changes:
                        p = safe_path(root, change.path)
                        old = p.read_text(encoding="utf-8") if p.exists() else None
                        if old is not None and snapshot.get(change.path) != old:
                            raise ValueError(
                                f"File changed since snapshot or not included: {change.path}"
                            )
                        proposals.append(
                            {
                                "path": change.path,
                                "content": change.content,
                                "before_hash": hashlib.sha256(
                                    (old or "").encode()
                                ).hexdigest(),
                                "existed": old is not None,
                                "diff": "".join(
                                    difflib.unified_diff(
                                        (old or "").splitlines(True),
                                        change.content.splitlines(True),
                                        fromfile=f"a/{change.path}",
                                        tofile=f"b/{change.path}",
                                    )
                                ),
                            }
                        )
                    if proposals:
                        if not await self.approval(
                            task, "changes", {"changes": proposals}
                        ):
                            raise ValueError("Changes rejected")
                        # Revalidate every file before writing any file.
                        for change in proposals:
                            p = safe_path(root, change["path"])
                            old = p.read_text(encoding="utf-8") if p.exists() else ""
                            if (
                                p.exists() != change["existed"]
                                or hashlib.sha256(old.encode()).hexdigest()
                                != change["before_hash"]
                            ):
                                raise ValueError(
                                    "Workspace changed after approval; rerun required"
                                )
                        for change in proposals:
                            p = safe_path(root, change["path"])
                            p.parent.mkdir(parents=True, exist_ok=True)
                            safe_path(root, change["path"]).write_text(
                                change["content"], encoding="utf-8"
                            )
                            emit(
                                "tool.completed",
                                tool="workspace.write",
                                message=change["path"],
                                diff=change["diff"],
                            )
                    task["result"] = result.model_dump()
                    task["status"] = "running"
                    self.store.save(
                        "tasks",
                        task,
                        "agent.working",
                        message="Applying approved result",
                    )
                    if result.test_suite != "none":
                        outcome = await run_tests(root, result.test_suite)
                        task["result"]["test_result"] = outcome
                        if outcome.get("executed") is False:
                            result.status = "blocked"
                            task["result"]["status"] = "blocked"
                            task["result"]["summary"] = "Manual test verification required; Docker and automated project tests are disabled"
                            task["result"]["findings"].append(outcome["output"])
                            task["status"] = "blocked"
                            emit("tests.manual_required", tool="tests.manual", **outcome)
                            self.store.save("tasks", task, "task.blocked", message=task["result"]["summary"])
                            return
                        emit("tool.completed", tool="sandbox.test", **outcome)
                        if outcome["exit_code"] != 0:
                            raise ValueError(
                                "Sandbox tests failed; see execution output"
                            )
                    elif task["agent_id"] == "qa":
                        result.summary = "Manual QA verification required; no project tests were executed"
                        task["result"]["summary"] = result.summary
                        result.status = "blocked"
                        task["result"]["status"] = "blocked"
                        task["result"]["findings"].append(
                            "QA execution requires manual verification. Docker and automated project tests are disabled; no tests were run."
                        )
                    if result.status == "blocked":
                        task["status"] = "blocked"
                        self.store.save(
                            "tasks", task, "task.blocked", message=result.summary
                        )
                        return
                task["status"] = "completed"
                self.store.save(
                    "tasks", task, "task.completed", message=task["result"]["summary"]
                )
        except asyncio.CancelledError:
            task["status"] = "cancelled"
            self.store.save(
                "tasks", task, "task.cancelled", message="Cancelled by user"
            )
        except Exception as e:
            task["status"] = "failed"
            task["error"] = str(e)[:2000]
            self.store.save("tasks", task, "task.failed", message=task["error"])
        finally:
            self.store.save(
                "runs",
                {
                    "id": task["run_id"],
                    "task_id": task["id"],
                    "project_id": task["project_id"],
                    "agent_id": task["agent_id"],
                    "status": task["status"],
                    "completed_at": now(),
                    "attempt": task["attempts"],
                    "result": task.get("result"),
                    "error": task.get("error"),
                },
                "run.finished",
                message=task["status"],
            )
            self.active.pop(task["id"], None)
