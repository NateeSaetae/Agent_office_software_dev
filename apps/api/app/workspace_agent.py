"""Application-managed read/search/write/command loop with bounded tool calls."""
from __future__ import annotations
import asyncio
import difflib
import hashlib
import json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, create_model
from .security import safe_path, files, qa_artifact_path, devops_config_path
from .local_runner import command_spec, run_local


class Edit(BaseModel):
    path: str
    content: str = Field(max_length=200_000)


class StepBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["list", "read", "search", "write", "command", "finish"]
    path: str
    query: str
    command: Literal["none", "install", "typecheck", "build", "test"]
    changes: list[Edit] = Field(max_length=20)


class WorkspaceAgent:
    def __init__(self, root, role, provider, approve, emit, settings, known):
        self.root, self.role, self.provider = root, role, provider
        self.approve, self.emit, self.settings, self.known = approve, emit, settings, dict(known)
        self.results = []
        self.revision = 0
        self.mutations = 0
        self.needs_verification = False

    async def write(self, changes):
        edits=[Edit.model_validate(c) for c in changes]
        if not edits: raise ValueError("No changes supplied")
        if len(edits)>20 or len({e.path for e in edits})!=len(edits): raise ValueError("Invalid change batch")
        if self.mutations>=8: raise ValueError("Write batch limit reached")
        if self.role in {"planner","reviewer"}: raise ValueError("This role is read-only")
        proposals=[]
        for edit in edits:
            if self.role=="qa" and not qa_artifact_path(edit.path): raise ValueError("QA can write test files and QA documents only")
            if self.role=="devops" and not devops_config_path(edit.path): raise ValueError("DevOps can write local build/configuration only; no Docker")
            p=safe_path(self.root,edit.path)
            old=p.read_text(encoding="utf-8") if p.exists() else None
            if old is not None and self.known.get(edit.path)!=old: raise ValueError(f"Read the current file before writing: {edit.path}")
            proposals.append({"path":edit.path,"content":edit.content,"existed":old is not None,"before_hash":hashlib.sha256((old or "").encode()).hexdigest(),"diff":"".join(difflib.unified_diff((old or "").splitlines(True),edit.content.splitlines(True),fromfile="a/"+edit.path,tofile="b/"+edit.path))})
        if not await self.approve("changes",{"changes":proposals}): raise PermissionError("Changes rejected")
        for change in proposals:
            p=safe_path(self.root,change["path"])
            old=p.read_text(encoding="utf-8") if p.exists() else ""
            if p.exists()!=change["existed"] or hashlib.sha256(old.encode()).hexdigest()!=change["before_hash"]: raise ValueError("Workspace changed after approval")
        for change in proposals:
            p=safe_path(self.root,change["path"]); p.parent.mkdir(parents=True,exist_ok=True)
            safe_path(self.root,change["path"]).write_text(change["content"],encoding="utf-8")
            self.known[change["path"]]=change["content"]
            self.emit("tool.completed",tool="workspace.write",message=change["path"],diff=change["diff"])
        self.needs_verification |= any(Path(e.path).suffix.lower() not in {".md", ".txt"} for e in edits)
        self.revision+=1; self.mutations+=1
        return {"written":[e.path for e in edits],"revision":self.revision}

    async def command(self, path, command):
        if self.role=="planner": raise ValueError("Planner cannot execute commands")
        root=safe_path(self.root,path or ".")
        if not root.is_dir(): raise ValueError("Command working directory does not exist")
        argv=command_spec(root,command)
        payload={"command":command,"argv":argv,"cwd":str(root),"timeout_seconds":300 if command=="install" else 180,"execution":"local host process; not an OS sandbox","network":"dependency installation may access package registries" if command=="install" else "project script may access network"}
        if not await self.approve("commands",payload): raise PermissionError("Local command rejected")
        self.emit("tool.started",tool="local.command",message=f"Running {command} in {path or '.'}",**payload)
        outcome=await run_local(root,command,payload["timeout_seconds"])
        if command == "install" and outcome["exit_code"] == 0: self.revision += 1
        outcome.update({"path":path or ".","revision":self.revision})
        self.results.append(outcome)
        self.emit("tool.completed",tool="local.command",message=f"{command}: exit {outcome['exit_code']}",**outcome)
        return outcome

    async def run(self, instructions, context, final_type):
        step_type=create_model("WorkspaceStep",__base__=StepBase,result=(final_type|None,...))
        guide='''\nUse the application-managed tool protocol in the output schema. Each response requests ONE action or finishes. Always include path, query, command (none when unused), changes (empty when unused), and result (null except finish). Available tools: list (refresh file index), read (relative file), search (literal text across source), write (approved full file replacements), command (install/typecheck/build/test in relative project subdirectory). Tool results are supplied in tool_history and override stale starter-snapshot contents. You CAN inspect additional files and execute these application-owned commands; do not use native tools. Read files before modifying. Use write before command, inspect real output and fix errors before finish. Do not return changes inside final result; apply them through write first. Never claim test success without a successful command tool result with test_count>0. Commands run locally without Docker, are bounded, and need approval unless auto workflow was authorized. Prefer relevant reads to copying the whole repository. Do not install or execute Docker, deploy, push, or delete files. Stop with a precise blocker when tool limits or missing requirements prevent completion. QA must execute tests; developers should verify available typecheck/build/test scripts. Planner: read/list/search only and return a Plan. Reviewers: read/search/verification only. Ignore old task descriptions that claim Docker or all tools are mandatory/unavailable: use the capabilities described here. Do not inspect or modify Agent Office source. Finish only the assigned project task. Limits: 24 model/tool steps, 8 write batches; subprocess timeouts apply.'''
        history=[]
        for turn in range(24):
            raw=await asyncio.wait_for(self.provider.generate(instructions+guide,json.dumps({**context,"tool_history":history[-16:]},ensure_ascii=False),step_type.model_json_schema(),self.emit,**self.settings),360)
            # Compatibility with existing contract providers/older structured responses.
            if "action" not in raw: return raw
            step=step_type.model_validate(raw)
            self.emit("agent.tool_requested",tool="workspace."+step.action,message=f"Step {turn+1}: {step.action}")
            if step.action=="finish":
                if step.result is None: raise ValueError("Finish needs a result")
                final=step.result.model_dump()
                if final.get("changes"):
                    output=await self.write(final["changes"])
                    history.append({"action":"write","output":output,"instruction":"Changes applied. Verify them before finishing with changes=[]"})
                    continue
                latest=[r for r in self.results if r["revision"]==self.revision]
                failures={}
                for r in latest: failures[(r["path"],r["command"])]=r
                bad=[r for r in failures.values() if r["exit_code"]!=0]
                if bad and final.get("status")=="completed":
                    history.append({"action":"finish_rejected","output":"Latest verification failed; fix errors or report blocked","failures":bad})
                    continue
                if self.needs_verification and self.role in {"frontend","backend","devops"} and final.get("status")=="completed" and not any(r["command"] in {"test","build","typecheck"} and r["exit_code"]==0 for r in latest):
                    history.append({"action":"finish_rejected","output":"Source/configuration changed: execute a real build/typecheck/test after the last write, or report blocked"})
                    continue
                if self.role=="qa" and final.get("status")=="completed" and not any(r["command"]=="test" and r["exit_code"]==0 and r["test_count"]>0 for r in latest):
                    history.append({"action":"finish_rejected","output":"QA requires executed tests after the last write; request command=test or report blocked"})
                    continue
                # Evidence is attached by the orchestrator; no caller-supplied test pass.
                return final
            try:
                if step.action=="list": output={"files":files(self.root)}
                elif step.action=="read":
                    p=safe_path(self.root,step.path)
                    if not p.is_file() or p.stat().st_size>200000: raise ValueError("File missing or over 200 KB")
                    content=p.read_text(encoding="utf-8",errors="replace");self.known[step.path]=content
                    output={"path":step.path,"content":content}
                elif step.action=="search":
                    if not step.query or len(step.query)>200: raise ValueError("Search query must be 1–200 characters")
                    matches=[]
                    for name in files(self.root):
                        for n,line in enumerate(safe_path(self.root,name).read_text(encoding="utf-8",errors="replace").splitlines(),1):
                            if step.query.casefold() in line.casefold():matches.append({"path":name,"line":n,"text":line[:300]})
                            if len(matches)>=80:break
                        if len(matches)>=80:break
                    output={"matches":matches}
                elif step.action=="write": output=await self.write([e.model_dump() for e in step.changes])
                else: output=await self.command(step.path,step.command)
            except PermissionError: raise
            except (ValueError,OSError,TimeoutError) as error:
                output={"error":str(error)[:2000]}
                self.emit("tool.failed",tool="workspace."+step.action,message=str(error)[:1000])
            history.append({"action":step.action,"path":step.path,"output":output})
            # Bound feedback context without losing the latest result.
            while len(json.dumps(history,ensure_ascii=False))>70000 and len(history)>1: history.pop(0)
        raise ValueError("Agent tool-step limit reached (24); inspect logs before retry")
