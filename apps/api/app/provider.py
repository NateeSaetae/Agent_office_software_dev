"""Codex SDK adapter. The model proposes changes; application tools apply them."""

from __future__ import annotations
import asyncio
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Protocol
from openai_codex import AsyncCodex, CodexConfig, ApprovalMode


class Provider(Protocol):
    async def generate(
        self, instructions: str, prompt: str, schema: dict, emit: Any, *, model: str | None = None, reasoning: str | None = None
    ) -> dict: ...


class CodexProvider:
    def __init__(self, runtime_dir: Path):
        runtime_dir.mkdir(parents=True, exist_ok=True)
        home = runtime_dir.parent / "codex-home"
        home.mkdir(parents=True, exist_ok=True)
        hook_args = [
            sys.executable,
            str(Path(__file__).with_name("deny_native_tools.py")),
        ]
        hook_command = (
            subprocess.list2cmdline(hook_args)
            if os.name == "nt"
            else shlex.join(hook_args)
        )
        hooks = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {"type": "command", "command": hook_command, "timeout": 5}
                        ],
                    }
                ]
            }
        }
        (home / "hooks.json").write_text(json.dumps(hooks), encoding="utf-8")
        self.config = CodexConfig(
            cwd=str(runtime_dir),
            env={"CODEX_HOME": str(home)},
            config_overrides=(
                "features.hooks=true",
                "features.prefer_mxc=true",
                'windows.sandbox="elevated"',
                'default_permissions="office"',
                # Elevated Windows sandbox requires root read access to initialize.
                'permissions.office.filesystem={":root"="read",":minimal"="read",":workspace_roots"={"."="read"}}',
                "permissions.office.network.enabled=false",
                "features.shell_tool=false",
                "features.apply_patch_freeform=false",
                "features.js_repl=false",
                "features.code_mode=false",
                "features.multi_agent=false",
                'web_search="disabled"',
            ),
        )

    def client(self) -> AsyncCodex:
        return AsyncCodex(self.config)

    async def account(self) -> dict:
        async with self.client() as client:
            result = await client.account()
            account = result.account
            if not account:
                return {"connected": False, "provider": "codex"}
            obj = account.model_dump(mode="json", by_alias=True)
            if "root" in obj:
                obj = obj["root"]
            return {
                "connected": obj.get("type") == "chatgpt",
                "provider": "codex",
                "plan": obj.get("planType"),
                "auth_type": obj.get("type"),
            }

    async def models(self) -> list[dict]:
        async with self.client() as client:
            catalog = await client.models()
        return [
            {
                "model": m.model,
                "name": m.display_name,
                "description": m.description,
                "is_default": m.is_default,
                "default_reasoning": str(getattr(m.default_reasoning_effort, "value", m.default_reasoning_effort)),
                "reasoning_efforts": [
                    {"value": str(getattr(r.reasoning_effort, "value", r.reasoning_effort)), "description": r.description}
                    for r in m.supported_reasoning_efforts
                ],
            }
            for m in catalog.data if not m.hidden
        ]

    async def generate(
        self, instructions: str, prompt: str, schema: dict, emit: Any, *, model: str | None = None, reasoning: str | None = None
    ) -> dict:
        async with self.client() as client:
            thread = await client.thread_start(
                approval_mode=ApprovalMode.deny_all,
                ephemeral=True,
                developer_instructions=instructions,
                model=model,
            )
            handle = await thread.turn(prompt, output_schema=schema, effort=reasoning)
            emit("runtime.started", thread_id=thread.id, turn_id=handle.id, requested_model=model, requested_reasoning=reasoning, message=f"Model: {model or 'Runtime default'} · reasoning: {reasoning or 'Model default'}")
            try:
                result = await asyncio.wait_for(handle.run(), 300)
            except BaseException:
                try:
                    await asyncio.wait_for(handle.interrupt(), 10)
                except Exception:
                    pass
                raise
            if str(getattr(result.status, "value", result.status)) != "completed":
                raise RuntimeError(f"Codex turn ended: {result.status}")
            # No claims of built-in tool results: all execution is application-owned.
            emit("runtime.completed", thread_id=thread.id, turn_id=handle.id)
            return json.loads(result.final_response or "{}")
