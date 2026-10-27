"""Application-owned tools. No arbitrary host shell execution."""

from __future__ import annotations
import asyncio
import os
import re
import shutil
import tempfile
from pathlib import Path

SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".scss",
    ".json",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
    ".txt",
    ".sql",
    ".sh",
    ".ps1",
    ".xml",
    ".csv",
}
DENIED = {
    ".git",
    ".env",
    ".ssh",
    ".aws",
    ".codex",
    "node_modules",
    ".venv",
    "__pycache__",
    ".data",
    "dist",
    "work",
    ".kube",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
}


def safe_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or ":" in relative or "\\" in relative:
        raise ValueError("Only relative workspace paths are allowed")
    if any(
        p.lower() in DENIED
        or p.lower().startswith(".env.")
        or p.lower().endswith((".pem", ".key", ".p12", ".pfx", ".sqlite", ".db"))
        for p in rel.parts
    ):
        raise ValueError("Protected path")
    candidate = root / rel
    for parent in [candidate, *candidate.parents]:
        if parent == root.parent:
            break
        if parent.is_symlink() or (
            hasattr(parent, "is_junction") and parent.is_junction()
        ):
            raise ValueError("Links and junctions are not allowed")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("Path escapes workspace")
    return resolved


def files(root: Path) -> list[str]:
    result: list[str] = []
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [
            d
            for d in dirs
            if d.lower() not in DENIED
            and not (Path(base) / d).is_symlink()
            and not (
                hasattr(Path(base) / d, "is_junction")
                and (Path(base) / d).is_junction()
            )
        ]
        for name in names:
            try:
                p = safe_path(root, (Path(base) / name).relative_to(root).as_posix())
                if (
                    p.is_file()
                    and p.suffix.lower() in SOURCE_EXTENSIONS
                    and p.stat().st_size <= 200_000
                ):
                    result.append(p.relative_to(root).as_posix())
            except ValueError:
                pass
            if len(result) >= 500:
                return result
    return result


async def _docker_test(root: Path, suite: str, timeout: int = 120) -> dict:
    """Fixed commands only; untrusted tests run without host credentials/network."""
    choices = {
        "python": ("python:3.12-slim", ["python", "-m", "unittest", "discover", "-v"]),
        "node": ("node:22-slim", ["node", "--test"]),
    }
    if suite not in choices:
        raise ValueError("Unknown test suite")
    image, command = choices[suite]
    import uuid

    name = f"natee-test-{uuid.uuid4().hex[:12]}"
    argv = [
        "docker",
        "run",
        "--name",
        name,
        "--rm",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=128",
        "--memory=512m",
        "--cpus=1",
        "--user=65534:65534",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--mount",
        f"type=bind,source={root},target=/workspace,readonly",
        "-w",
        "/workspace",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        image,
        *command,
    ]
    proc = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    try:
        output, _ = await asyncio.wait_for(proc.communicate(), timeout)
        decoded = output.decode(errors="replace")[-30000:]
        match = (
            re.search(r"Ran (\d+) tests?", decoded)
            if suite == "python"
            else re.search(r"# tests (\d+)", decoded)
        )
        count = int(match.group(1)) if match else 0
        return {
            "exit_code": proc.returncode if count > 0 else 1,
            "process_exit_code": proc.returncode,
            "test_count": count,
            "output": decoded
            if count > 0
            else decoded + "\nNo executed tests detected.",
            "suite": suite,
        }
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        try:
            cleanup = await asyncio.create_subprocess_exec(
                "docker",
                "rm",
                "-f",
                name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(cleanup.wait(), 10)
        except (OSError, TimeoutError):
            pass


async def docker_test(root: Path, suite: str, timeout: int = 120) -> dict:
    # Only approved source types are staged; .env/credentials are never mounted.
    with tempfile.TemporaryDirectory(prefix="natee-tests-") as temp:
        stage = Path(temp)
        for relative in files(root):
            source = safe_path(root, relative)
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        return await _docker_test(stage, suite, timeout)
