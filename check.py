"""Run the backend contract tests in isolated temporary workspaces."""

import os
import sys
import uuid
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path[:0] = [str(root / ".python-deps"), str(root / "apps/api")]
temp = root / "work" / "tmp"
temp.mkdir(parents=True, exist_ok=True)
os.environ["TEMP"] = os.environ["TMP"] = str(temp)
import pytest

raise SystemExit(
    pytest.main(
        [
            str(root / "apps/api/tests"),
            "-q",
            "--basetemp",
            str(root / "work" / ("tests-" + uuid.uuid4().hex[:8])),
        ]
    )
)
