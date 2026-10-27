import asyncio
from pathlib import Path
import pytest
from app.security import safe_path, files
from app.store import Store
from app.orchestrator import Orchestrator, Plan, validate_plan


@pytest.mark.parametrize(
    "path",
    [
        "../escape.txt",
        "/etc/passwd",
        "C:/Windows/file",
        ".env",
        ".env.local",
        ".git/config",
        "keys/private.pem",
        "foo\\bar",
    ],
)
def test_protected_paths(tmp_path: Path, path: str):
    with pytest.raises(ValueError):
        safe_path(tmp_path, path)


def test_nested_sources_and_secret_exclusion(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.ts").write_text("export const a = 1")
    (tmp_path / ".env").write_text("TOKEN=secret")
    assert files(tmp_path) == ["src/app.ts"]


def test_event_persistence_and_replay(tmp_path: Path):
    db = tmp_path / "office.db"
    s = Store(db)
    s.save("projects", {"id": "p", "name": "P"}, "project.created")
    s.emit("runtime.started", agent_id="planner")
    reopened = Store(db)
    assert reopened.get("projects", "p")["name"] == "P"
    assert [e["id"] for e in reopened.events(1)] == [2]


def test_cycle_rejected():
    plan = Plan(
        summary="test",
        tasks=[
            dict(
                key="a",
                agent_id="qa",
                title="a",
                description="a",
                acceptance_criteria=[],
                depends_on=["b"],
            ),
            dict(
                key="b",
                agent_id="reviewer",
                title="b",
                description="b",
                acceptance_criteria=[],
                depends_on=["a"],
            ),
        ],
    )
    with pytest.raises(ValueError):
        validate_plan(plan)


class FakeProvider:
    """Contract test fixture, never enabled in the running application."""

    def __init__(self, result):
        self.result = result

    async def generate(self, *args):
        return self.result


def setup(tmp_path, result, agent="frontend"):
    root = tmp_path / "source"
    root.mkdir()
    s = Store(tmp_path / "db.sqlite")
    s.save(
        "projects",
        {"id": "p", "workspace": str(root), "requirement": "Build a tiny function"},
        "project.created",
    )
    o = Orchestrator(s, FakeProvider(result))
    t = {
        "id": "t",
        "project_id": "p",
        "agent_id": agent,
        "title": "Implement",
        "description": "Implement",
        "status": "pending",
        "attempts": 0,
        "depends_on": [],
        "acceptance_criteria": [],
    }
    return root, s, o, t


async def wait_approval(o):
    for _ in range(200):
        if o.waiters:
            return next(iter(o.waiters))
        await asyncio.sleep(0.005)
    raise AssertionError("Approval never arrived")


def result(changes=None):
    return {
        "status": "completed",
        "summary": "Done",
        "findings": [],
        "changes": changes or [],
        "test_suite": "none",
    }


def test_write_requires_exact_approval(tmp_path):
    async def scenario():
        root, s, o, t = setup(
            tmp_path, result([{"path": "app.py", "content": "VALUE = 42\n"}])
        )
        o.queue(t)
        a = await wait_approval(o)
        assert not (root / "app.py").exists()
        o.decide(a, True)
        await o.active["t"]
        assert (root / "app.py").read_text() == "VALUE = 42\n"
        assert s.get("tasks", "t")["status"] == "completed"
        assert s.get("approvals", a)["status"] == "approved"
        with pytest.raises(ValueError):
            o.decide(a, True)

    asyncio.run(scenario())


def test_rejection_leaves_workspace_unchanged(tmp_path):
    async def scenario():
        root, s, o, t = setup(tmp_path, result([{"path": "app.py", "content": "x"}]))
        o.queue(t)
        a = await wait_approval(o)
        o.decide(a, False)
        await o.active["t"]
        assert not (root / "app.py").exists()
        assert s.get("tasks", "t")["status"] == "failed"

    asyncio.run(scenario())


def test_workspace_change_invalidates_approval(tmp_path):
    async def scenario():
        root, s, o, t = setup(
            tmp_path, result([{"path": "app.py", "content": "proposal"}])
        )
        (root / "app.py").write_text("original")
        o.queue(t)
        a = await wait_approval(o)
        (root / "app.py").write_text("user edit")
        o.decide(a, True)
        await o.active["t"]
        assert (root / "app.py").read_text() == "user edit"
        assert s.get("tasks", "t")["status"] == "failed"

    asyncio.run(scenario())


def test_cancel_expires_pending_approval(tmp_path):
    async def scenario():
        root, s, o, t = setup(tmp_path, result([{"path": "app.py", "content": "x"}]))
        o.queue(t)
        a = await wait_approval(o)
        running = o.active["t"]
        o.cancel("t")
        await running
        assert not (root / "app.py").exists()
        assert s.get("tasks", "t")["status"] == "cancelled"
        assert s.get("approvals", a)["status"] == "expired"

    asyncio.run(scenario())


def test_qa_cannot_complete_without_tests(tmp_path):
    async def scenario():
        root, s, o, t = setup(tmp_path, result(), agent="qa")
        o.queue(t)
        await o.active["t"]
        assert s.get("tasks", "t")["status"] == "blocked"

    asyncio.run(scenario())


@pytest.mark.parametrize("path", ["mini-todo/QA.md", "docs/test-plan.md", "mini-todo/tests/checklist.md"])
def test_qa_document_requires_approval_and_remains_unverified(tmp_path, path):
    async def scenario():
        root, s, o, t = setup(tmp_path, result([
            {"path": path, "content": "# QA\nBuild: not tested\n"}
        ]), agent="qa")
        o.queue(t)
        approval = await wait_approval(o)
        assert not (root / path).exists()
        o.decide(approval, True)
        await o.active["t"]
        assert (root / path).read_text() == "# QA\nBuild: not tested\n"
        assert s.get("tasks", "t")["status"] == "blocked"
        assert "Manual QA verification" in s.get("tasks", "t")["result"]["summary"]
    asyncio.run(scenario())


@pytest.mark.parametrize("path", ["mini-todo/src/App.tsx", "mini-todo/package.json", "src.test.folder/App.tsx"])
def test_qa_rejects_application_changes_with_filename(tmp_path, path):
    async def scenario():
        root, s, o, t = setup(tmp_path, result([
            {"path": path, "content": "not allowed"}
        ]), agent="qa")
        o.queue(t)
        await o.active["t"]
        saved = s.get("tasks", "t")
        assert saved["status"] == "failed"
        assert path in saved["error"]
        assert not (root / path).exists()
        assert not o.waiters
    asyncio.run(scenario())


def test_readonly_role_cannot_write(tmp_path):
    async def scenario():
        root, s, o, t = setup(
            tmp_path, result([{"path": "x.py", "content": "x"}]), agent="reviewer"
        )
        o.queue(t)
        await o.active["t"]
        assert not (root / "x.py").exists()
        assert s.get("tasks", "t")["status"] == "failed"

    asyncio.run(scenario())


def test_restart_does_not_resubmit_work(tmp_path):
    root, s, o, t = setup(tmp_path, result())
    t["status"] = "running"
    s.save("tasks", t, "task.running")
    o.recover()
    assert s.get("tasks", "t")["status"] == "interrupted"
    assert not o.active


def test_sequential_workflow_respects_dependencies(tmp_path):
    async def scenario():
        root, s, o, t = setup(tmp_path, result())
        t["status"] = "pending"
        s.save("tasks", t, "task.created")
        other = {**t, "id": "t2", "depends_on": ["t"]}
        s.save("tasks", other, "task.created")
        o.start_workflow("p")
        pipeline = o.pipeline
        await pipeline
        assert s.get("tasks", "t")["status"] == "completed"
        assert s.get("tasks", "t2")["status"] == "completed"
        assert len(s.all("runs")) == 2
        assert s.recent()[-1]["type"] == "workflow.completed"

    asyncio.run(scenario())


def test_retry_limit(tmp_path):
    async def scenario():
        root, s, o, t = setup(tmp_path, result())
        t["attempts"] = 3
        before = dict(t)
        with pytest.raises(ValueError):
            o.queue(t)
        assert not o.active
        assert t == before

    asyncio.run(scenario())


@pytest.mark.parametrize("status", ["failed", "blocked", "cancelled", "interrupted"])
def test_explicit_retry_after_limit_preserves_attempt_history(tmp_path, status):
    async def scenario():
        root, s, o, t = setup(tmp_path, result())
        t.update(status=status, attempts=3, error="Previous configuration error")
        o.queue(t, manual_retry=True)
        await o.active["t"]
        saved = s.get("tasks", "t")
        assert saved["status"] == "completed"
        assert saved["attempts"] == 4
        assert "error" not in saved
        assert s.all("runs")[0]["attempt"] == 4
    asyncio.run(scenario())


def test_pipeline_cannot_override_retry_limit(tmp_path):
    async def scenario():
        root, s, o, t = setup(tmp_path, result())
        t.update(status="failed", attempts=3)
        with pytest.raises(ValueError, match="Automatic retry limit"):
            o.queue(t, from_pipeline=True, manual_retry=True)
        assert not o.active
        assert t["attempts"] == 3
    asyncio.run(scenario())


def test_qa_feedback_creates_bounded_repair(tmp_path, monkeypatch):
    import app.orchestrator as module

    class SequenceProvider:
        async def generate(self, instructions, *args):
            return {
                **result(),
                "test_suite": "python"
                if "Inspect acceptance criteria" in instructions
                else "none",
            }

    calls = 0

    async def fake_test(*args):
        nonlocal calls
        calls += 1
        return {
            "exit_code": 1 if calls == 1 else 0,
            "test_count": 1,
            "output": "verified fixture failure" if calls == 1 else "passed",
        }

    monkeypatch.setattr(module, "run_tests", fake_test)

    async def scenario():
        root, s, o, t = setup(tmp_path, result())
        t["status"] = "completed"
        s.save("tasks", t, "task.completed")
        qa = {
            **t,
            "id": "qa",
            "agent_id": "qa",
            "status": "pending",
            "depends_on": ["t"],
            "attempts": 0,
        }
        s.save("tasks", qa, "task.created")
        o.provider = SequenceProvider()
        o.start_workflow("p")
        pipeline = o.pipeline
        while o.pipeline:
            if o.waiters:
                o.decide(next(iter(o.waiters)), True)
            await asyncio.sleep(0.005)
        await pipeline
        assert s.get("tasks", "qa")["status"] == "completed"
        assert s.get("tasks", "qa")["attempts"] == 2
        assert any(e["type"] == "qa.feedback" for e in s.recent())

    asyncio.run(scenario())

def test_manual_test_mode_never_spawns_process(tmp_path, monkeypatch):
    from app.security import run_tests, test_policy

    async def forbidden(*args, **kwargs):
        raise AssertionError("Manual mode must not spawn Docker or a host shell")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    for suite in ("python", "node"):
        outcome = asyncio.run(run_tests(tmp_path, suite))
        assert outcome["executed"] is False
        assert outcome["exit_code"] is None
        assert outcome["test_count"] == 0
    assert test_policy()["mode"] == "manual"


def test_old_test_request_becomes_manual_blocker(tmp_path):
    async def scenario():
        root, s, o, t = setup(tmp_path, {**result(), "test_suite": "node"})
        o.queue(t)
        await o.active["t"]
        saved = s.get("tasks", "t")
        assert saved["status"] == "blocked"
        assert saved["result"]["test_result"]["executed"] is False
        assert not o.waiters
        assert any(e["type"] == "tests.manual_required" for e in s.recent())
    asyncio.run(scenario())


@pytest.mark.parametrize("path", ["package.json", "tsconfig.json", "vite.config.ts", "scripts/start.ps1", "docs/local-run.md", "mini-todo/index.html", "mini-todo/.gitignore", "mini-todo/src/vite-env.d.ts"])
def test_devops_local_configuration_allowed(path):
    from app.security import devops_config_path
    assert devops_config_path(path)


@pytest.mark.parametrize("path", ["Dockerfile", "infra/Dockerfile.prod", "docker-compose.yaml", "compose.yml", "infra/.dockerignore", "src/App.tsx"])
def test_devops_container_and_app_changes_rejected(path):
    from app.security import devops_config_path
    assert not devops_config_path(path)


def test_devops_vite_entry_requires_approval(tmp_path):
    async def scenario():
        root, s, o, t = setup(tmp_path, result([
            {"path": "mini-todo/index.html", "content": '<div id="root"></div>'},
            {"path": "mini-todo/package.json", "content": '{}'},
        ]), agent="devops")
        o.queue(t)
        approval = await wait_approval(o)
        assert not (root / "mini-todo/index.html").exists()
        o.decide(approval, True)
        await o.active["t"]
        assert s.get("tasks", "t")["status"] == "completed"
        assert (root / "mini-todo/index.html").read_text() == '<div id="root"></div>'
    asyncio.run(scenario())


def test_devops_rejection_names_file_without_writing(tmp_path):
    async def scenario():
        root, s, o, t = setup(tmp_path, result([
            {"path": "mini-todo/index.html", "content": '<div id="root"></div>'},
            {"path": "mini-todo/src/App.tsx", "content": 'export default () => null'},
        ]), agent="devops")
        o.queue(t)
        await o.active["t"]
        saved = s.get("tasks", "t")
        assert saved["status"] == "failed"
        assert "mini-todo/src/App.tsx" in saved["error"]
        assert not (root / "mini-todo/index.html").exists()
        assert not o.waiters
    asyncio.run(scenario())


@pytest.mark.parametrize("path", ["mini-todo/vite.config.mjs", "vite.config.mts", "vitest.config.cjs"])
def test_devops_module_configuration_allowed(path):
    from app.security import devops_config_path
    assert devops_config_path(path)


def test_skip_preserves_history_and_unblocks_workflow(tmp_path):
    async def scenario():
        root, s, o, t = setup(tmp_path, result())
        t.update(status="failed", attempts=3, error="Configuration failed")
        s.save("tasks", t, "task.failed")
        child = {**t, "id": "child", "status": "pending", "attempts": 0, "depends_on": ["t"]}
        s.save("tasks", child, "task.created")
        skipped = o.skip("t")
        assert skipped["status"] == "skipped"
        assert skipped["attempts"] == 3
        assert skipped["error"] == "Configuration failed"
        assert not list(root.iterdir())
        assert not s.all("runs")
        o.start_workflow("p")
        await o.pipeline
        assert s.get("tasks", "t")["status"] == "skipped"
        assert s.get("tasks", "child")["status"] == "completed"
        assert any(e["type"] == "task.skipped" for e in s.recent())
    asyncio.run(scenario())


@pytest.mark.parametrize("status", ["running", "queued", "awaiting_approval", "completed", "skipped"])
def test_skip_rejects_active_or_finished_status(tmp_path, status):
    root, s, o, t = setup(tmp_path, result())
    t["status"] = status
    s.save("tasks", t, "task.created")
    with pytest.raises(ValueError):
        o.skip("t")
    assert s.get("tasks", "t")["status"] == status
