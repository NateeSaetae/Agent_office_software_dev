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
        with pytest.raises(ValueError):
            o.queue(t)
        assert not o.active

    asyncio.run(scenario())


def test_qa_feedback_creates_bounded_repair(tmp_path, monkeypatch):
    import app.orchestrator as module

    class SequenceProvider:
        async def generate(self, instructions, *args):
            return {
                **result(),
                "test_suite": "python"
                if "run available fixed sandbox tests" in instructions
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

    monkeypatch.setattr(module, "docker_test", fake_test)

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
