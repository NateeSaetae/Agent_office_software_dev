import json
from types import SimpleNamespace
import pytest
from app.model_settings import agent_settings, validate_selection
from app.store import Store
from app.provider import CodexProvider
import app.provider as provider_module

CATALOG = [{"model": "fixture-model", "name": "Fixture", "reasoning_efforts": [{"value": "high", "description": "Detailed"}]}]


def test_selection_validation():
    assert validate_selection(CATALOG, "fixture-model", "high") == {"model": "fixture-model", "reasoning": "high"}
    assert validate_selection([], None, None) == {"model": None, "reasoning": None}
    for model, effort in [("missing", None), ("fixture-model", "unsupported"), (None, "high")]:
        with pytest.raises(ValueError):
            validate_selection(CATALOG, model, effort)


def test_agent_preferences_persist_independently(tmp_path):
    path = tmp_path / "prefs.sqlite"
    store = Store(path)
    assert agent_settings(store, "planner") == {"model": None, "reasoning": None}
    store.save("agent_settings", {"id": "planner", "model": "fixture-model", "reasoning": "high"}, "agent.settings_updated")
    reopened = Store(path)
    assert agent_settings(reopened, "planner")["reasoning"] == "high"
    assert agent_settings(reopened, "frontend")["model"] is None
    with pytest.raises(KeyError):
        agent_settings(reopened, "not-an-agent")
    reopened.engine.dispose()
    store.engine.dispose()


def complete(coroutine):
    # All fixture awaits complete immediately; no socket/event-loop permissions or network needed.
    try:
        coroutine.send(None)
    except StopIteration as done:
        return done.value
    raise AssertionError("Unexpected IO in model-selection contract test")


def test_provider_passes_model_and_reasoning_to_sdk(monkeypatch):
    seen = {}
    class Handle:
        id = "turn-fixture"
        async def run(self):
            return SimpleNamespace(status="completed", final_response=json.dumps({"summary": "fixture"}))
    class Thread:
        id = "thread-fixture"
        async def turn(self, prompt, **kwargs):
            seen["turn"] = kwargs
            return Handle()
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def thread_start(self, **kwargs):
            seen["thread"] = kwargs
            return Thread()
    async def immediate(awaitable, timeout): return await awaitable
    monkeypatch.setattr(provider_module.asyncio, "wait_for", immediate)
    provider = object.__new__(CodexProvider)
    provider.client = lambda: Client()
    events = []
    result = complete(provider.generate("instructions", "input", {}, lambda *a, **kw: events.append(kw), model="fixture-model", reasoning="high"))
    assert result["summary"] == "fixture"
    assert seen["thread"]["model"] == "fixture-model"
    assert seen["turn"]["effort"] == "high"
    assert events[0]["requested_model"] == "fixture-model"


def test_queued_run_freezes_preferences(tmp_path, monkeypatch):
    from app.orchestrator import Orchestrator
    import app.orchestrator as module
    store = Store(tmp_path / "queue.sqlite")
    store.save("agent_settings", {"id": "planner", "model": "fixture-model", "reasoning": "high"}, "agent.settings_updated")
    def capture(coroutine):
        coroutine.close()
        return object()
    monkeypatch.setattr(module.asyncio, "create_task", capture)
    o = Orchestrator(store, object())
    task = {"id": "task", "project_id": "project", "agent_id": "planner", "status": "pending", "attempts": 0}
    o.queue(task)
    store.save("agent_settings", {"id": "planner", "model": None, "reasoning": None}, "agent.settings_updated")
    assert task["model_settings"] == {"model": "fixture-model", "reasoning": "high"}
    assert store.get("runs", task["run_id"])["model_settings"] == task["model_settings"]
    store.engine.dispose()

def test_settings_api_validates_and_state_exposes_preferences(tmp_path, monkeypatch):
    import importlib
    from fastapi import HTTPException
    monkeypatch.setenv("NATEE_DATA_DIR", str(tmp_path / "api-data"))
    module = importlib.import_module("app.main")
    store = Store(tmp_path / "api-models.sqlite")
    monkeypatch.setattr(module, "store", store)
    class CatalogProvider:
        async def models(self): return CATALOG
    monkeypatch.setattr(module, "provider", CatalogProvider())
    async def immediate(awaitable, timeout): return await awaitable
    monkeypatch.setattr(module.asyncio, "wait_for", immediate)
    chosen = complete(module.save_agent_settings("planner", module.AgentModelSettings(model="fixture-model", reasoning="high")))
    assert chosen["model"] == "fixture-model"
    planner = next(a for a in module.state()["agents"] if a["id"] == "planner")
    assert planner["settings"]["reasoning"] == "high"
    with pytest.raises(HTTPException) as invalid:
        complete(module.save_agent_settings("planner", module.AgentModelSettings(model="fixture-model", reasoning="invalid")))
    assert invalid.value.status_code == 400
    assert agent_settings(store, "planner")["reasoning"] == "high"
    with pytest.raises(HTTPException) as missing:
        complete(module.save_agent_settings("unknown", module.AgentModelSettings()))
    assert missing.value.status_code == 404
    complete(module.save_agent_settings("planner", module.AgentModelSettings()))
    assert agent_settings(store, "planner") == {"model": None, "reasoning": None}
    store.engine.dispose()

def test_bulk_preferences_validate_all_before_saving(tmp_path, monkeypatch):
    import importlib
    from fastapi import HTTPException
    monkeypatch.setenv("NATEE_DATA_DIR", str(tmp_path / "bulk-api-data"))
    module = importlib.import_module("app.main")
    store = Store(tmp_path / "bulk.sqlite")
    monkeypatch.setattr(module, "store", store)
    class CatalogProvider:
        async def models(self): return CATALOG
    monkeypatch.setattr(module, "provider", CatalogProvider())
    async def immediate(awaitable, timeout): return await awaitable
    monkeypatch.setattr(module.asyncio, "wait_for", immediate)
    def request(settings):
        return complete(module.save_bulk_agent_settings(module.BulkAgentPreferences(settings=settings)))
    valid = {"agent_id": "frontend", "model": "fixture-model", "reasoning": "high"}
    with pytest.raises(HTTPException) as invalid:
        request([valid, {"agent_id": "backend", "model": "fixture-model", "reasoning": "unsupported"}])
    assert invalid.value.status_code == 400
    assert store.all("agent_settings") == []
    assert store.recent() == []
    with pytest.raises(HTTPException): request([valid, valid])
    with pytest.raises(HTTPException): request([{**valid, "agent_id": "unknown"}])
    request([valid, {"agent_id": "backend", "model": None, "reasoning": None}])
    reopened = Store(tmp_path / "bulk.sqlite")
    assert agent_settings(reopened, "frontend") == {"model": "fixture-model", "reasoning": "high"}
    assert agent_settings(reopened, "backend") == {"model": None, "reasoning": None}
    assert len(reopened.recent()) == 1
    with pytest.raises(HTTPException): request([{**valid, "model": None}])
    assert agent_settings(reopened, "frontend")["model"] == "fixture-model"
    reopened.engine.dispose()
    store.engine.dispose()
