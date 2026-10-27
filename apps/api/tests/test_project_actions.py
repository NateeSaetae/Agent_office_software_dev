from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from app.store import Store
from app.project_workspace import workspace_path, remove_workspace


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setenv("NATEE_DATA_DIR", str(tmp_path / "bootstrap"))
    from app import main

    root = tmp_path / "agent-office"
    data = root / ".data"
    data.mkdir(parents=True)
    storage = Store(data / "test.db")
    monkeypatch.setattr(main, "ROOT", root)
    monkeypatch.setattr(main, "DATA", data)
    monkeypatch.setattr(main, "store", storage)
    monkeypatch.setattr(
        main,
        "orchestrator",
        SimpleNamespace(active={}, pipeline=None, recover=lambda: None),
    )
    with TestClient(main.app) as client:
        client.get("/api/session")
        yield client, main, storage, tmp_path
    storage.engine.dispose()


def create(client, **extra):
    result = client.post(
        "/api/projects",
        json={
            "name": "Disposable test project",
            "requirement": "Build a small task tracker",
            **extra,
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def delete(client, project, **extra):
    return client.post(
        f"/api/projects/{project['id']}/delete",
        json={
            "confirmation_name": project["name"],
            "workspace": project["workspace"],
            **extra,
        },
    )


def test_deletes_workspace_and_project_records_preserves_other_project(office):
    client, main, store, tmp = office
    project = create(client)
    other = create(client, name="Keep this project")
    root = Path(project["workspace"])
    (root / "nested").mkdir()
    (root / "nested" / "source.ts").write_text("export const value = 1")
    (root / ".hidden").write_text("temporary fixture")
    for kind in ("tasks", "runs", "approvals"):
        store.save(
            kind,
            {
                "id": "delete-" + kind,
                "project_id": project["id"],
                "agent_id": "devops",
                "status": "blocked",
            },
            "test.created",
        )
        store.save(
            kind,
            {
                "id": "keep-" + kind,
                "project_id": other["id"],
                "agent_id": "devops",
                "status": "completed",
            },
            "test.created",
        )
    assert delete(client, project).status_code == 200
    assert not root.exists()
    assert Path(other["workspace"]).is_dir()
    with pytest.raises(KeyError):
        store.get("projects", project["id"])
    for kind in ("tasks", "runs", "approvals"):
        assert [r["id"] for r in store.all(kind)] == ["keep-" + kind]
    assert [
        e["type"] for e in store.events() if e.get("project_id") == project["id"]
    ] == ["project.deleted"]
    assert delete(client, project).status_code == 404


def test_deletes_dedicated_custom_workspace(office):
    client, main, store, tmp = office
    root = tmp / "custom-project"
    root.mkdir()
    (root / "app.ts").write_text("// temporary test")
    project = create(client, workspace=str(root))
    assert delete(client, project).status_code == 200
    assert not root.exists()


def test_confirmation_and_busy_guards_preserve_files(office):
    client, main, store, tmp = office
    project = create(client)
    assert delete(client, project, confirmation_name="wrong").status_code == 409
    assert delete(client, project, workspace=str(tmp)).status_code == 409
    main.orchestrator.active["test"] = SimpleNamespace(
        cancel=lambda: None, __await__=lambda: None
    )
    assert delete(client, project).status_code == 409
    main.orchestrator.active.clear()
    main.orchestrator.pipeline = SimpleNamespace(done=lambda: False)
    assert delete(client, project).status_code == 409
    main.orchestrator.pipeline = None
    assert Path(project["workspace"]).exists()
    assert store.get("projects", project["id"])


def test_missing_folder_can_remove_stale_project(office):
    client, main, store, tmp = office
    project = create(client)
    Path(project["workspace"]).rmdir()
    assert delete(client, project).status_code == 200


def test_protects_source_data_home_and_shared_workspaces(office):
    client, main, store, tmp = office
    project = create(client)
    protected = [
        main.ROOT,
        main.ROOT / "apps",
        main.DATA,
        Path.home(),
        Path(main.ROOT.anchor),
    ]
    for root in protected:
        edited = {**project, "workspace": str(root)}
        store.save("projects", edited, "test.updated")
        assert delete(client, edited).status_code == 409, str(root)
    store.delete_project(project)
    root = tmp / "shared"
    root.mkdir()
    first = create(client, name="First", workspace=str(root))
    nested = root / "nested"
    nested.mkdir()
    second = create(client, name="Second", workspace=str(nested))
    assert delete(client, first).status_code == 409
    assert delete(client, second).status_code == 409
    assert nested.exists()


def test_filesystem_failure_preserves_project(office, monkeypatch):
    client, main, store, tmp = office
    project = create(client)

    def fail(root):
        raise PermissionError("File is open")

    monkeypatch.setattr(main, "remove_workspace", fail)
    result = delete(client, project)
    assert result.status_code == 409
    assert "File is open" in result.json()["detail"]
    assert store.get("projects", project["id"])
    assert Path(project["workspace"]).exists()


def test_folder_action_returns_full_path_and_uses_stored_directory(office, monkeypatch):
    client, main, store, tmp = office
    project = create(client)
    calls = []
    monkeypatch.setattr(main, "open_workspace", lambda root: calls.append(root) or True)
    result = client.post(f"/api/projects/{project['id']}/open-folder", json={})
    assert result.status_code == 200
    assert result.json() == {"opened": True, "workspace": project["workspace"]}
    assert calls == [Path(project["workspace"])]
    monkeypatch.setattr(main, "open_workspace", lambda root: False)
    assert (
        client.post(f"/api/projects/{project['id']}/open-folder", json={}).json()[
            "opened"
        ]
        is False
    )


def test_nested_symlink_refused_without_touching_target(tmp_path):
    root = tmp_path / "project"
    external = tmp_path / "outside"
    root.mkdir()
    external.mkdir()
    important = external / "keep.txt"
    important.write_text("keep")
    try:
        (root / "linked").symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is not permitted on this host")
    with pytest.raises(ValueError, match="link or junction"):
        remove_workspace(root)
    assert important.read_text() == "keep"
    with pytest.raises(ValueError, match="links or junctions"):
        workspace_path(
            {"id": "p", "workspace": str(root / "linked")},
            [],
            tmp_path / "office",
            tmp_path / "office/.data",
        )
