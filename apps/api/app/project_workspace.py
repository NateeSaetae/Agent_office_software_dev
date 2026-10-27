"""Project folder actions, restricted to dedicated non-overlapping workspaces."""

from __future__ import annotations
import os
import shutil
import stat
from pathlib import Path


def _linked(path: Path) -> bool:
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        return True
    try:
        return bool(
            getattr(path.lstat(), "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
    except FileNotFoundError:
        return False


def workspace_path(
    project: dict, projects: list[dict], app_root: Path, data_root: Path
) -> Path:
    raw = Path(project["workspace"])
    if not raw.is_absolute():
        raise ValueError("Workspace must be an absolute directory")
    for part in (raw, *raw.parents):
        if _linked(part):
            raise ValueError(
                "Workspace paths containing links or junctions cannot be used for folder actions"
            )
    root = raw.resolve()
    app_root, data_root = app_root.resolve(), data_root.resolve()
    managed = root == data_root / "workspaces" / project["id"]
    protected = [
        Path.home().resolve(),
        app_root,
        data_root,
        *[Path.home() / name for name in (".codex", ".ssh", ".aws", "AppData")],
    ]
    for key in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramData", "PUBLIC"):
        if os.environ.get(key):
            protected.append(Path(os.environ[key]).resolve())
    if root == Path(root.anchor) or any(
        root == p or root in p.parents for p in protected
    ):
        raise ValueError(
            "This folder is protected; choose a dedicated project workspace"
        )
    if not managed and any(
        root.is_relative_to(p) for p in [app_root, data_root, *protected[3:]]
    ):
        raise ValueError(
            "Agent Office source, app data and system folders cannot be removed"
        )
    for other in projects:
        if other["id"] == project["id"]:
            continue
        other_root = Path(other["workspace"]).resolve()
        if root.is_relative_to(other_root) or other_root.is_relative_to(root):
            raise ValueError(
                "Workspace overlaps another project; its folder cannot be removed"
            )
    if root.exists() and not root.is_dir():
        raise ValueError("Workspace is no longer a directory")
    return root


def remove_workspace(root: Path) -> None:
    # The absolute target is validated by workspace_path before this call.
    # Refuse nested reparse points instead of risking traversal outside the folder.
    if not root.exists():
        return

    def fail(error: OSError) -> None:
        raise error

    for base, dirs, names in os.walk(root, followlinks=False, onerror=fail):
        for name in [*dirs, *names]:
            if _linked(Path(base) / name):
                raise ValueError(
                    "Workspace contains a link or junction. Remove the link before deleting the project"
                )
    shutil.rmtree(root)


def open_workspace(root: Path) -> bool:
    if not root.is_dir():
        raise ValueError("Workspace folder does not exist")
    if os.name != "nt":
        return False
    try:
        os.startfile(str(root), "open")
        return True
    except OSError:
        return False
