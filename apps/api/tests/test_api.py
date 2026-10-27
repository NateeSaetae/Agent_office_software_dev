import os
from fastapi.testclient import TestClient


def test_session_origin_and_project_creation(tmp_path):
    if True:
        os.environ["NATEE_DATA_DIR"] = str(tmp_path)
        from app.main import app, store

        with TestClient(app) as client:
            assert client.get("/api/state").status_code == 401
            assert (
                client.get(
                    "/api/session", headers={"Origin": "https://evil.example"}
                ).status_code
                == 403
            )
            assert client.get("/api/session").status_code == 200
            body = client.get("/api/state").json()
            assert len(body["agents"]) == 6
            assert body["tasks"] == []
            response = client.post(
                "/api/projects",
                json={
                    "name": "Contract test",
                    "requirement": "Create a small task manager",
                },
            )
            assert response.status_code == 200
            assert response.json()["name"] == "Contract test"
            assert (
                client.post(
                    "/api/projects",
                    json={"name": "x", "workspace": "C:/", "requirement": "Something"},
                ).status_code
                == 400
            )
            assert (
                client.post(
                    "/api/projects",
                    headers={"Origin": "https://evil.example"},
                    json={"name": "x", "requirement": "Something"},
                ).status_code
                == 403
            )
            with client.websocket_connect(
                "/ws", headers={"origin": "http://127.0.0.1:8000"}
            ) as ws:
                assert "events" in ws.receive_json()
        store.engine.dispose()
        os.environ.pop("NATEE_DATA_DIR", None)
