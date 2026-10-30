"""Application-owned tools. No arbitrary host shell execution."""

from __future__ import annotations
import os
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
    ".office-runtime",
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


def qa_artifact_path(relative: str) -> bool:
    """Allow tests and named QA documents, including nested project folders."""
    path = Path(relative)
    name = path.name.lower()
    return (
        any(part in {"tests", "__tests__"} for part in path.parts[:-1])
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
        or name in {"qa.md", "testing.md", "test-plan.md", "test-results.md", "qa-report.md"}
    )


def devops_config_path(relative: str) -> bool:
    """DevOps may prepare local build/run configuration, never containers."""
    path = Path(relative)
    name = path.name.lower()
    if name.startswith(("dockerfile", "docker-compose", "compose.")) or name == ".dockerignore" or name in {
        "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"
    }:
        return False
    return relative.startswith(("infra/", ".github/workflows/", "scripts/", "docs/")) or name in {
        "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
        "pyproject.toml", "requirements.txt", "requirements-dev.txt",
        "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json",
        "vite.config.ts", "vite.config.js", "vitest.config.ts", "vitest.config.js",
        "vite.config.mjs", "vite.config.mts", "vite.config.cjs", "vite.config.cts",
        "vitest.config.mjs", "vitest.config.mts", "vitest.config.cjs", "vitest.config.cts",
        ".nvmrc", ".node-version", "makefile", "readme.md",
        "index.html", ".gitignore", "vite-env.d.ts"
    }


def test_policy() -> dict:
    return {"ready": True, "mode": "local", "message": "Local install/typecheck/build/test commands are available with approval or an explicitly authorized auto workflow. Docker is disabled. Project scripts run on this PC, not in an OS sandbox."}


async def run_tests(root: Path, suite: str, timeout: int = 180) -> dict:
    if suite not in {"python", "node"}: raise ValueError("Unknown test suite")
    from .local_runner import run_local
    return await run_local(root, "test", timeout)
