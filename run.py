"""Launch using either a normal environment or bundled local dependencies."""

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
deps = root / ".python-deps"
if deps.exists():
    sys.path.insert(0, str(deps))
sys.path.insert(0, str(root / "apps" / "api"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.environ.get("NATEE_PORT", "8000")),
        ws="websockets",
    )
