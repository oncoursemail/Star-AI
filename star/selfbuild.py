"""STAR improves its own skill modules in an isolated Git worktree.

Autonomous routine edits; no per-operation prompts. The model CANNOT write
core permissions, security files, tests, credentials or workflow definitions.
Generated code is only syntax checked, never executed by this builder.
"""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
from typing import Any

from .github_app import BRANCH, GitHubApp


def skill_path(path: str) -> bool:
    if not isinstance(path, str) or len(path) > 170 or "\\" in path:
        return False
    p = PurePosixPath(path)
    if path != p.as_posix() or p.is_absolute() or ".." in p.parts or any(x.startswith(".") for x in p.parts):
        return False
    if path == "star/skills/__init__.py":
        return False  # Keep potential auto-import registration under human control.
    return ((path.startswith("star/skills/") and path.endswith(".py")) or
            (path.startswith("docs/skills/") and path.endswith(".md")))


def _target(workspace: Path, name: str) -> Path:
    if not skill_path(name):
        raise ValueError("Self-build path restricted to star/skills/*.py and docs/skills/*.md")
    root = workspace.resolve()
    dest = (root / name).resolve()
    if not dest.is_relative_to(root):
        raise ValueError("Symlink/path traversal disallowed")
    return dest


def read_source(workspace: Path, name: str) -> str:
    p = _target(workspace, name)
    if not p.exists():
        return "File does not exist."
    if not p.is_file() or p.stat().st_size > 80_000:
        raise ValueError("Invalid or oversized source")
    return p.read_text(encoding="utf-8")


def write_source(workspace: Path, name: str, source: str) -> str:
    p = _target(workspace, name)
    if len(source) > 40_000:
        raise ValueError("File too long")
    if name.endswith(".py"):
        compile(source, str(p), "exec")  # syntax verification, NOT execution
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(source, encoding="utf-8")
    return f"Wrote {name} ({len(source)} chars); Python syntax check passed if applicable."


def run_git(*args: str, cwd: Path):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30,
                            encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError("Git operation failed: " + result.stderr[-1200:])
    return result.stdout.strip()


TOOLS = [
    {"type":"function", "function":{"name":"list_skill_files","description":"List the files that STAR's self-builder is allowed to edit.","parameters":{"type":"object","properties":{},"additionalProperties":False}}},
    {"type":"function", "function":{"name":"read_skill_file","description":"Read only star/skills/*.py or docs/skills/*.md.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"],"additionalProperties":False}}},
    {"type":"function", "function":{"name":"write_skill_file","description":"Write a new or improved Python skill module or skill documentation in the isolated Git worktree. Do not execute generated Python.","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"],"additionalProperties":False}}},
]


async def develop(*, client, model: str, repository: Path, task: str,
                  github: GitHubApp | None = None, max_turns: int = 10) -> dict[str, Any]:
    repository = repository.resolve()
    if not (repository / ".git").exists():
        # .git can be a file in a worktree; both are allowed once repository is initialized.
        raise RuntimeError("Initialize and commit this repository before STAR self-build")
    if run_git("status", "--porcelain", cwd=repository):
        raise RuntimeError("Commit your pending changes before autonomous self-build")
    branch = "star/skill-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    if not BRANCH.fullmatch(branch):
        raise RuntimeError("Bad auto-generated branch")
    folder = Path(tempfile.mkdtemp(prefix="star-builder-"))
    active = False
    try:
        run_git("worktree", "add", "-b", branch, str(folder), "HEAD", cwd=repository)
        active = True
        messages = [
            {"role": "system", "content": "You are STAR Self-Builder. Improve STAR's skill modules incrementally. Allowed writes are only star/skills/*.py and docs/skills/*.md. Make one meaningful small improvement. Favor testable pure utility functions, clear docstrings and type hints. Do not claim tests ran, do not invent repository files, and do not ask for destructive permissions. No unsafe execution, network calls, or auto-imported generated code. Do not try to edit security policy or build system."},
            {"role": "user", "content": task},
        ]
        notes=[]
        for step in range(max_turns):
            response = await client.chat.completions.create(model=model, messages=messages, tools=TOOLS, tool_choice="auto", temperature=0, max_tokens=1800)
            msg = response.choices[0].message
            if not msg.tool_calls:
                notes.append((msg.content or "No summary").strip())
                break
            messages.append({"role":"assistant", "content":msg.content or "", "tool_calls":[
                {"id": tc.id,"type":"function","function":{"name":tc.function.name,"arguments":tc.function.arguments}} for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                try:
                    args=json.loads(tc.function.arguments)
                    name=tc.function.name
                    if name=="list_skill_files" and args=={}:
                        value="\n".join(sorted(p.relative_to(folder).as_posix() for root in (folder/"star"/"skills", folder/"docs") for p in root.rglob("*") if p.is_file() and skill_path(p.relative_to(folder).as_posix())))[:7000]
                    elif name=="read_skill_file" and set(args)=={"path"}:
                        value=read_source(folder, args["path"])
                    elif name=="write_skill_file" and set(args)=={"path","content"}:
                        value=write_source(folder, args["path"], args["content"])
                    else:
                        raise ValueError("Unknown or malformed self-build operation")
                    result={"ok":True,"message":value[:17000]}
                except Exception as exc:
                    result={"ok":False,"error":type(exc).__name__,"detail":str(exc)[:400]}
                messages.append({"role":"tool","tool_call_id":tc.id,"content":json.dumps(result)})
        run_git("diff", "--check", cwd=folder)
        stage_paths = [p for p in ("star/skills", "docs") if (folder / p).exists()]
        if not stage_paths:
            raise RuntimeError("No allowed source directories exist")
        run_git("add", "--", *stage_paths, cwd=folder)
        paths = run_git("diff", "--cached", "--name-only", cwd=folder).splitlines()
        if not paths:
            raise RuntimeError("No allowed files changed; self-build produced no accepted patch")
        if any(not skill_path(p) for p in paths):
            raise RuntimeError("Out-of-scope files appeared in the staged patch")
        run_git("-c", "user.name=STAR Genesis", "-c", "user.email=star-builder@users.noreply.github.com", "commit", "-m", "STAR: propose skill improvement", cwd=folder)
        commit=run_git("rev-parse", "HEAD", cwd=folder)
        payload={"branch":branch, "commit":commit, "files":paths,"model_notes":notes,"github_pr":None,
                 "verification":"Python syntax validated on written files; generated behavior has NOT been executed or verified"}
        if github is not None:
            # Publishing via installation token does not merge anything or update main.
            base=await github.create_branch(branch)
            for path in paths:
                await github.write_branch_file(branch,path,(folder/path).read_bytes(),"STAR: propose " + path)
            pr=await github.open_pr(base,branch,"STAR self-build: candidate skill improvement", "Generated in isolated worktree. Python syntax was checked. Tests/review required before merging.\n\n" + "\n".join(notes)[:5000])
            payload["github_pr"]=pr.get("html_url")
        return payload
    finally:
        if active:
            try:
                run_git("worktree", "remove", "--force", str(folder), cwd=repository)
            except Exception:
                pass
        shutil.rmtree(folder, ignore_errors=True)
