"""Build an isolated Rojo project one validated Luau module per model call.

Plan JSON: {"modules": [{"name": "Inventory", "kind": "server",
"purpose": "...", "interface": ["getItem"], "requires": ["Items"]}]}.
The model callable accepts one prompt string and returns a string.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from typing import Callable

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_FENCE = re.compile(r"```(?:lua|luau)?[ \t]*\n(.*?)\n```", re.I | re.S)
_FORBIDDEN = re.compile(
    r"\b(?:loadstring|getfenv|setfenv|dofile|loadfile)\s*\("
    r"|\b(?:HttpService|TeleportService|DataStoreService|MessagingService)\b"
    r"|\b(?:game|workspace)\s*:\s*HttpGet\s*\("
    r"|\b(?:require)\s*\(\s*\d+\s*\)", re.I
)
_LOCATIONS = {
    "server": ("ServerScriptService", "Server"),
    "client": ("StarterPlayer", "StarterPlayerScripts", "Client"),
    "shared": ("ReplicatedStorage", "Shared"),
}


def ordered_modules(plan: dict | list) -> list[dict]:
    """Validate all identifiers and dependencies before any filesystem mutation."""
    modules = plan.get("modules") if isinstance(plan, dict) else plan
    if not isinstance(modules, list) or not modules:
        raise ValueError("Plan needs a non-empty modules list")
    by_name = {}
    for item in modules:
        if not isinstance(item, dict):
            raise ValueError("Every module must be an object")
        name = item.get("name")
        if not isinstance(name, str) or not _NAME.fullmatch(name) or name in by_name:
            raise ValueError("Invalid or duplicate module name")
        if item.get("kind") not in _LOCATIONS:
            raise ValueError(f"Invalid kind for {name}")
        if not isinstance(item.get("purpose"), str) or not item["purpose"].strip():
            raise ValueError(f"Missing purpose for {name}")
        interface = item.get("interface")
        requires = item.get("requires", [])
        if not isinstance(interface, list) or not interface or any(
            not isinstance(s, str) or not _NAME.fullmatch(s) for s in interface
        ):
            raise ValueError(f"Invalid interface for {name}")
        if not isinstance(requires, list) or any(
            not isinstance(s, str) or not _NAME.fullmatch(s) for s in requires
        ) or len(requires) != len(set(requires)):
            raise ValueError(f"Invalid dependencies for {name}")
        by_name[name] = {**item, "requires": requires}
    for name, item in by_name.items():
        if name in item["requires"] or any(dep not in by_name for dep in item["requires"]):
            raise ValueError(f"Unknown or self dependency for {name}")
    result, active, done = [], set(), set()

    def visit(name: str) -> None:
        if name in active:
            raise ValueError("Cyclic module dependencies")
        if name in done:
            return
        active.add(name)
        for dep in by_name[name]["requires"]:
            visit(dep)
        active.remove(name)
        done.add(name)
        result.append(by_name[name])

    for name in by_name:
        visit(name)
    return result


def validate_code(response: str, interface: list[str]) -> tuple[str | None, str | None]:
    """Conservative static check; not a Luau parser or runtime security boundary."""
    matches = _FENCE.findall(response) if isinstance(response, str) else []
    if len(matches) != 1 or not matches[0].strip():
        return None, "Expected exactly one non-empty fenced Luau code block"
    code = matches[0].strip() + "\n"
    # Strip comments to avoid accepting interface names or forbidden calls inside comments.
    uncommented = re.sub(r"--\[=*\[.*?\]=*\]", "", code, flags=re.S)
    uncommented = re.sub(r"--[^\n]*", "", uncommented)
    if _FORBIDDEN.search(uncommented):
        return None, "Forbidden API detected"
    for name in interface:
        escaped = re.escape(name)
        if not re.search(
            rf"\b(?:function\s+\w+\.{escaped}\s*\(|\w+\.{escaped}\s*=\s*function\s*\()",
            uncommented,
        ):
            return None, f"Missing public interface: {name}"
    if not re.search(r"\breturn\s+\w+", uncommented):
        return None, "Module must return its public table"
    return code, None


def _file_under(root: Path, relative: Path) -> Path:
    """Block traversal and symlink escapes, including on preexisting ancestors."""
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("Output path escapes selected folder")
    root = root.resolve()
    target = root / relative
    if not target.resolve().is_relative_to(root):
        raise ValueError("Output path escapes selected folder")
    return target


def _write_new(root: Path, relative: Path, content: str) -> None:
    target = _file_under(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    # x mode prevents accidentally overwriting existing project files.
    with target.open("x", encoding="utf-8") as handle:
        handle.write(content)


def _rojo_project() -> dict:
    return {
        "name": "STARGenerated",
        "tree": {
            "$className": "DataModel",
            "ServerScriptService": {"$path": "src/ServerScriptService"},
            "ReplicatedStorage": {"$path": "src/ReplicatedStorage"},
            "StarterPlayer": {
                "$className": "StarterPlayer",
                "StarterPlayerScripts": {"$path": "src/StarterPlayer/StarterPlayerScripts"},
            },
        },
    }


def build_project(plan: dict | list, out: str | Path, generate: Callable[[str], str]) -> dict:
    modules = ordered_modules(plan)
    root = Path(out).expanduser().resolve()
    # Preflight every path before writing any file.
    paths = [Path("src").joinpath(*_LOCATIONS[m["kind"]], m["name"] + ".lua")
             for m in modules]
    reserved = [Path("default.project.json"), Path("manifest.json"), *paths]
    for relative in reserved:
        target = _file_under(root, relative)
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Refusing to overwrite {relative}")
    root.mkdir(parents=True, exist_ok=True)
    result = {"generated": [], "failed": []}
    by_name = {m["name"]: m for m in modules}
    for module, relative in zip(modules, paths):
        summaries = [
            {"name": dep, "kind": by_name[dep]["kind"],
             "interface": by_name[dep]["interface"]}
            for dep in module["requires"]
        ]
        brief = {key: module[key] for key in ("name", "kind", "purpose", "interface", "requires")}
        prompt = (
            "Write exactly one Roblox Luau ModuleScript in one fenced luau code block. "
            "Expose all named functions on a returned table. No network, datastore, "
            "dynamic evaluation or asset-id require APIs. "
            "You receive dependency interface summaries only, not source code.\n"
            + json.dumps({"module": brief, "dependency_interfaces": summaries})
        )
        error = None
        code = None
        attempts = 0
        for attempts in (1, 2):
            response = generate(prompt if error is None else prompt + "\nPrevious failure: " + error)
            code, error = validate_code(response, module["interface"])
            if error is None:
                break
        if error is not None:
            result["failed"].append({"name": module["name"], "attempts": attempts, "error": error})
            continue
        _write_new(root, relative, code)
        result["generated"].append({"name": module["name"], "kind": module["kind"],
                                     "path": relative.as_posix(), "attempts": attempts})
    _write_new(root, Path("default.project.json"), json.dumps(_rojo_project(), indent=2) + "\n")
    _write_new(root, Path("manifest.json"), json.dumps(result, indent=2) + "\n")
    return result


def _configured_generator() -> Callable[[str], str]:
    """Use the same configured local endpoint and model as STAR's CLI."""
    from openai import OpenAI
    from urllib.parse import urlsplit
    model = os.environ.get("STAR_MODEL", "").strip()
    endpoint = os.environ.get("STAR_BASE_URL", "http://127.0.0.1:1234/v1")
    parsed = urlsplit(endpoint)
    if not model or model == "your-loaded-lm-studio-model-id":
        raise ValueError("Configure STAR_MODEL before running the builder")
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.username or parsed.password:
        raise ValueError("Builder CLI supports only the configured loopback local model")
    client = OpenAI(base_url=endpoint, api_key="local-only", timeout=180.0, max_retries=0)
    def generate(prompt: str) -> str:
        reply = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}]
        )
        return reply.choices[0].message.content or ""
    return generate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a Rojo project from a module plan")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    manifest = build_project(plan, args.out, _configured_generator())
    print(json.dumps(manifest, indent=2))
    return 1 if manifest["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
