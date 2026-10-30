"""Fixed local project commands; cwd confinement is NOT an OS sandbox."""
from __future__ import annotations
import asyncio
import json
import os
import re
import shutil
import sys
import subprocess
from pathlib import Path
from .security import safe_path


def command_spec(root: Path, command: str) -> list[str]:
    if command not in {"install", "typecheck", "build", "test"}:
        raise ValueError("Allowed commands: install, typecheck, build, test")
    package = safe_path(root, "package.json")
    if package.exists():
        data = json.loads(package.read_text(encoding="utf-8"))
        scripts = data.get("scripts", {})
        npm = shutil.which("npm")
        node = shutil.which("node")
        if not npm or not node:
            raise ValueError("Node.js and npm must be installed locally")
        if os.name == "nt":
            cli = Path(npm).parent / "node_modules/npm/bin/npm-cli.js"
            if not cli.is_file():
                raise ValueError("Cannot locate npm-cli.js beside npm; install the official Node.js runtime")
            prefix = [node, str(cli)]
        else:
            prefix = [npm]
        if command == "install":
            return prefix + (["ci"] if safe_path(root, "package-lock.json").exists() else ["install"]) + ["--ignore-scripts", "--no-audit", "--no-fund"]
        if command not in scripts:
            if command == "test": return [node, "--test"]
            raise ValueError(f"package.json has no {command} script")
        if not isinstance(scripts[command], str): raise ValueError("Invalid package script")
        # npm invokes pre/post hooks itself, so block those hooks too.
        args = ["run", command, "--ignore-scripts"]
        if command == "test" and "vitest" in scripts[command] and "--run" not in scripts[command]:
            args += ["--", "--run"]
        return prefix + args
    if command == "test":
        tests = root / "tests"
        return [sys.executable, "-m", "unittest", "discover", "-s", "tests" if tests.is_dir() else ".", "-v"]
    if command == "typecheck":
        raise ValueError("No configured local typecheck command")
    if command == "install" and safe_path(root, "requirements.txt").exists():
        raise ValueError("Python dependency installation requires a project virtual environment; provision it manually first")
    raise ValueError("No supported local command configuration found")


def test_count(output: str) -> int:
    counts = []
    for pattern in [r"# tests\s+(\d+)", r"Ran (\d+) tests?", r"\b(\d+) passed\b", r"Tests:\s+(\d+) passed"]:
        counts += [int(n) for n in re.findall(pattern, output)]
    return max(counts, default=0)


async def _stop(proc):
    if proc.returncode is not None: return
    if os.name == "nt":
        killer = await asyncio.create_subprocess_exec("taskkill", "/PID", str(proc.pid), "/T", "/F", stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        try:
            await asyncio.wait_for(killer.wait(), 5)
        except TimeoutError:
            killer.kill()
        if proc.returncode is None:
            proc.kill()
    else:
        import signal
        os.killpg(proc.pid, signal.SIGKILL)
    await proc.wait()


async def run_local(root: Path, command: str, timeout: int = 180) -> dict:
    argv = command_spec(root, command)
    cache = root / ".office-runtime"
    if cache.is_symlink() or (hasattr(cache,"is_junction") and cache.is_junction()):
        raise ValueError("Runtime cache cannot be a link")
    cache.mkdir(exist_ok=True)
    if any(p.is_symlink() or (hasattr(p,"is_junction") and p.is_junction()) for p in cache.rglob("*")):
        raise ValueError("Runtime cache cannot contain links")
    for name in ["home", "tmp"]:
        folder=cache/name
        if folder.is_symlink() or (hasattr(folder,"is_junction") and folder.is_junction()): raise ValueError("Runtime cache cannot contain links")
        folder.mkdir(exist_ok=True)
    env = {k:v for k,v in os.environ.items() if k.upper() in {"PATH","PATHEXT","SYSTEMROOT","WINDIR","COMSPEC","NUMBER_OF_PROCESSORS","PROCESSOR_ARCHITECTURE"}}
    env.update({"HOME":str(cache/"home"),"USERPROFILE":str(cache/"home"),"APPDATA":str(cache/"home"),"LOCALAPPDATA":str(cache/"home"),"TEMP":str(cache/"tmp"),"TMP":str(cache/"tmp"),"CI":"true","PYTHONDONTWRITEBYTECODE":"1","npm_config_cache":str(cache/"npm-cache"),"npm_config_userconfig":str(cache/"empty-npmrc"),"npm_config_ignore_scripts":"true","npm_config_audit":"false","npm_config_fund":"false"})
    (cache/"empty-npmrc").write_text("",encoding="utf-8")
    flags={"creationflags":subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=="nt" else {"start_new_session":True}
    proc = await asyncio.create_subprocess_exec(*argv,cwd=str(root),env=env,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,**flags)
    output=bytearray()
    async def drain():
        while chunk:=await proc.stdout.read(4096):
            output.extend(chunk)
            if len(output)>60000: del output[:-60000]
        await proc.wait()
    try:
        await asyncio.wait_for(drain(), timeout)
    except (TimeoutError, asyncio.CancelledError):
        await asyncio.shield(_stop(proc))
        raise
    finally:
        if proc.returncode is None: await asyncio.shield(_stop(proc))
    text=output.decode(errors="replace")
    count=test_count(text) if command=="test" else 0
    code=proc.returncode
    if command=="test" and code==0 and count==0:
        code=1; text+="\nNo executed tests detected; this is not a verified test pass."
    return {"executed":True,"mode":"local","command":command,"argv":argv,"exit_code":code,"process_exit_code":proc.returncode,"test_count":count,"output":text[-30000:]}
