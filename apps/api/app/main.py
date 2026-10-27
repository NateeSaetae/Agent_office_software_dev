from __future__ import annotations
import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from .agents import AGENTS
from .store import Store, now
from .provider import CodexProvider
from .orchestrator import Orchestrator, uid
from .project_workspace import workspace_path, remove_workspace, open_workspace

ROOT = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("NATEE_DATA_DIR", str(ROOT / ".data"))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
store = Store(DATA / "office.db")
provider = CodexProvider(DATA / "runtime")
orchestrator = Orchestrator(store, provider)
TOKEN = secrets.token_urlsafe(32)
ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
}
ORIGINS.update(
    {
        f"http://127.0.0.1:{os.environ.get('NATEE_PORT', '8000')}",
        f"http://localhost:{os.environ.get('NATEE_PORT', '8000')}",
    }
)
login_handles: list = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    orchestrator.recover()
    yield
    pending = list(orchestrator.active.values())
    if orchestrator.pipeline:
        pending.append(orchestrator.pipeline)
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    for client, _, watcher in login_handles:
        watcher.cancel()
        await client.close()


app = FastAPI(title="Natee's Software House", lifespan=lifespan)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
)


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.url.path.startswith("/api"):
        origin = request.headers.get("origin")
        if origin and origin not in ORIGINS:
            return Response("Origin denied", 403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return Response("Cross-site access denied", 403)
        if request.url.path != "/api/session" and not secrets.compare_digest(
            request.cookies.get("office_session", ""), TOKEN
        ):
            return Response("Session required", 401)
    return await call_next(request)


@app.get("/api/session")
def session(response: Response):
    response.set_cookie(
        "office_session", TOKEN, httponly=True, samesite="strict", max_age=86400
    )
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True}


@app.get("/api/state")
def state():
    tasks = store.all("tasks")
    agents = []
    for a in AGENTS:
        assigned = [t for t in tasks if t["agent_id"] == a["id"]]
        active = next(
            (
                t
                for t in assigned
                if t["status"] in {"running", "queued", "awaiting_approval"}
            ),
            None,
        )
        agents.append(
            {**a, "status": active["status"] if active else "idle", "task": active}
        )
    return {
        "projects": store.all("projects"),
        "tasks": tasks,
        "agents": agents,
        "runs": store.all("runs"),
        "approvals": store.all("approvals"),
        "events": store.recent(),
        "busy": bool(orchestrator.active or orchestrator.pipeline),
    }


class NewProject(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    workspace: str = Field(default="", max_length=1000)
    requirement: str = Field(min_length=5, max_length=20000)


@app.post("/api/projects")
def create_project(body: NewProject):
    id = uid()
    if body.workspace.strip():
        root = Path(body.workspace).expanduser()
        if not root.is_absolute() or not root.is_dir():
            raise HTTPException(400, "Workspace must be an existing absolute directory")
        root = root.resolve()
        if (
            root == Path(root.anchor)
            or root == Path.home()
            or root == ROOT
            or root in ROOT.parents
            or root.is_relative_to(DATA)
        ):
            raise HTTPException(400, "Choose a dedicated project directory")
    else:
        root = DATA / "workspaces" / id
        root.mkdir(parents=True)
    project = {
        "id": id,
        "name": body.name.strip(),
        "workspace": str(root),
        "requirement": body.requirement,
        "created_at": now(),
    }
    store.save(
        "projects", project, "project.created", message=project["name"], project_id=id
    )
    return project


class DeleteProject(BaseModel):
    confirmation_name: str
    workspace: str


@app.post("/api/projects/{id}/open-folder")
async def open_project_folder(id: str):
    try:
        project = store.get("projects", id)
        root = workspace_path(project, store.all("projects"), ROOT, DATA)
        return {"opened": open_workspace(root), "workspace": str(root)}
    except KeyError:
        raise HTTPException(404, "Project not found")
    except (ValueError, OSError) as e:
        raise HTTPException(409, str(e))


@app.post("/api/projects/{id}/delete")
async def delete_project(id: str, body: DeleteProject):
    try:
        project = store.get("projects", id)
        if (
            body.confirmation_name != project["name"]
            or body.workspace != project["workspace"]
        ):
            raise HTTPException(
                409,
                "Project name or workspace changed. Check the project and confirm again",
            )
        if orchestrator.active or (
            orchestrator.pipeline and not orchestrator.pipeline.done()
        ):
            raise HTTPException(
                409,
                "Wait for the active run or workflow to stop before deleting a project",
            )
        root = workspace_path(project, store.all("projects"), ROOT, DATA)
        remove_workspace(root)
        store.delete_project(project)
        return {"ok": True, "workspace": str(root)}
    except KeyError:
        raise HTTPException(404, "Project not found")
    except ValueError as e:
        raise HTTPException(409, "Project was not removed: " + str(e))
    except OSError as e:
        raise HTTPException(
            409,
            "Folder deletion did not finish; some files may already be removed. Project record retained: "
            + str(e),
        )


async def require_account():
    try:
        account = await asyncio.wait_for(provider.account(), 30)
    except Exception as e:
        raise HTTPException(503, f"Codex unavailable: {e}")
    if not account.get("connected"):
        raise HTTPException(409, "Connect a ChatGPT account in Settings first")


@app.post("/api/projects/{id}/plan")
async def plan(id: str):
    try:
        project = store.get("projects", id)
        if orchestrator.active:
            raise HTTPException(409, "A run is already active")
        await require_account()
        project = store.get("projects", id)
        task = {
            "id": uid(),
            "project_id": id,
            "agent_id": "planner",
            "title": "Plan " + project["name"],
            "description": project["requirement"],
            "acceptance_criteria": ["Dependency-ordered tasks with QA and review"],
            "depends_on": [],
            "status": "pending",
            "attempts": 0,
            "created_at": now(),
        }
        orchestrator.queue(task)
        return task
    except KeyError:
        raise HTTPException(404, "Project not found")
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.post("/api/projects/{id}/workflow")
async def workflow(id: str):
    try:
        store.get("projects", id)
        await require_account()
        store.get("projects", id)
        orchestrator.start_workflow(id)
        return {"ok": True}
    except KeyError:
        raise HTTPException(404, "Project not found")
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.post("/api/tasks/{id}/run")
async def run_task(id: str):
    try:
        task = store.get("tasks", id)
        if task["status"] not in {
            "pending",
            "failed",
            "cancelled",
            "interrupted",
            "blocked",
        }:
            raise ValueError("Task cannot be started in its current state")
        for dep in task["depends_on"]:
            if store.get("tasks", dep)["status"] != "completed":
                raise ValueError("Complete dependencies first")
        await require_account()
        task = store.get("tasks", id)
        store.get("projects", task["project_id"])
        orchestrator.queue(task)
        return task
    except KeyError:
        raise HTTPException(404, "Task not found")
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.post("/api/tasks/{id}/cancel")
def cancel(id: str):
    try:
        orchestrator.cancel(id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(409, str(e))


class Decision(BaseModel):
    approve: bool


@app.post("/api/approvals/{id}")
def decide(id: str, body: Decision):
    try:
        orchestrator.decide(id, body.approve)
        return {"ok": True}
    except KeyError:
        raise HTTPException(404, "Approval not found")
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/api/account")
async def account():
    try:
        return await asyncio.wait_for(provider.account(), 30)
    except Exception as e:
        return {"connected": False, "provider": "codex", "error": str(e)[:1000]}


@app.get("/api/diagnostics")
async def diagnostics():
    checks = {}
    try:
        async with provider.client() as client:
            from openai_codex import ApprovalMode

            await asyncio.wait_for(
                client.thread_start(
                    approval_mode=ApprovalMode.deny_all, ephemeral=True
                ),
                25,
            )
        checks["codex_sandbox"] = {"ready": True}
    except Exception as e:
        checks["codex_sandbox"] = {"ready": False, "message": str(e)[-1200:]}
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "info",
            "--format",
            "{{.ServerVersion}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), 8)
            checks["docker"] = {
                "ready": proc.returncode == 0,
                "message": (out if proc.returncode == 0 else err).decode(
                    errors="replace"
                )[-1000:],
            }
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
    except Exception as e:
        checks["docker"] = {"ready": False, "message": str(e)[-1000:]}
    return checks


@app.post("/api/login")
async def login():
    if login_handles:
        return {"auth_url": login_handles[-1][1].auth_url}
    client = provider.client()
    try:
        await client.__aenter__()
        handle = await asyncio.wait_for(client.login_chatgpt(), 30)

        async def watch():
            try:
                await handle.wait()
                store.emit("account.connected", message="ChatGPT sign-in completed")
            except Exception:
                store.emit("account.failed", message="Sign-in failed or expired")
            finally:
                await client.close()
                login_handles.clear()

        watcher = asyncio.create_task(watch())
        login_handles.append((client, handle, watcher))
        return {"auth_url": handle.auth_url}
    except Exception as e:
        await client.close()
        raise HTTPException(503, str(e)[:1000])


@app.websocket("/ws")
async def events(ws: WebSocket):
    if ws.headers.get("origin") not in ORIGINS or not secrets.compare_digest(
        ws.cookies.get("office_session", ""), TOKEN
    ):
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        cursor = max(0, int(ws.query_params.get("after", "0")))
        while True:
            batch = store.events(cursor)
            if batch:
                await ws.send_json({"events": batch})
                cursor = batch[-1]["id"]
            else:
                await ws.send_json({"heartbeat": True})
            await asyncio.sleep(1)
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass


dist = ROOT / "apps" / "web" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")
