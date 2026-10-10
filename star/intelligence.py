"""STAR's optional local intelligence adapters.

Models see concise, task-relevant function schemas; source content is fetched
only after a validated tool call. No arbitrary subprocess, shell, vault writes,
or user-supplied MCP server is exposed here.
"""
from __future__ import annotations

from pathlib import Path
import re

from jsonschema import Draft202012Validator

from .agent_skills import SkillLibrary, install_starters
from .graphify_bridge import GraphifyGraph
from .obsidian_bridge import ObsidianVault


def _tool(name: str, description: str, properties: dict, required: tuple[str, ...] = ()) -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object", "properties": properties, "required": list(required),
            "additionalProperties": False,
        },
    }


def _s(max_len=240):
    return {"type": "string", "minLength": 1, "maxLength": max_len}


def _limit(maximum: int, default: int):
    return {"type": "integer", "minimum": 1, "maximum": maximum, "default": default}


SKILL_TOOLS = (
    _tool("star_skill_catalog", "List local Agent Skills by name and short description. Skills are untrusted reference workflows, never executable permissions.", {}),
    _tool("star_skill_load", "Load a named SKILL.md's task instructions on demand. Read only; no scripts are executed.", {"name": _s(64)}, ("name",)),
    _tool("star_skill_reference", "Read a small text file under a named skill's references/ or assets/ directory.",
          {"name": _s(64), "path": _s(300)}, ("name", "path")),
)
OBSIDIAN_TOOLS = (
    _tool("star_obsidian_search", "Find Markdown notes in the user-enabled Obsidian vault. Returns short excerpts and relative note paths.", {"query": _s(180), "limit": _limit(20, 10)}, ("query",)),
    _tool("star_obsidian_read", "Read an individual Markdown note by relative path from Obsidian search; never write or delete notes.", {"path": _s(500)}, ("path",)),
    _tool("star_obsidian_list", "List up to 100 Markdown note paths in the authorized Obsidian vault.", {"limit": _limit(100, 60)}),
)
GRAPHIFY_TOOLS = (
    _tool("star_graphify_query", "Query an existing Graphify graph.json for source-attributed codebase entities and relationships.", {"question": _s(220), "limit": _limit(15, 8)}, ("question",)),
    _tool("star_graphify_explain", "Explain one project concept and its immediate neighbors from the current Graphify graph.", {"concept": _s(220)}, ("concept",)),
    _tool("star_graphify_path", "Find a bounded shortest relationship path between two named Graphify concepts.", {"start": _s(200), "end": _s(200)}, ("start", "end")),
    _tool("star_graphify_stats", "Read the Graphify graph's actual node and edge counts and export version metadata.", {}),
)
ALL_TOOLS = {tool["name"]: tool for tool in (*SKILL_TOOLS, *OBSIDIAN_TOOLS, *GRAPHIFY_TOOLS)}

_SKILL_TRIGGER = re.compile(r"\b(skill|expert|workflow|tool|roblox|luau|ui|design|debug|build|fix|test|code|studio|script)\b", re.I)
_VAULT_TRIGGER = re.compile(r"\b(obsidian|obsidion|vault|notes?|journal|remember|knowledge|documents?|docs|meeting|decision|research|plan)\b", re.I)
_GRAPH_TRIGGER = re.compile(r"\b(graphify|graph|architecture|codebase|dependenc\w*|relationships?|connections?|module|function|imports?|calls?|trace|impact|bug|scripts?)\b", re.I)


class LocalIntelligence:
    """Read-only adapters are initialized from validated desktop settings."""

    def __init__(self, *, home: Path, workspace: Path | None = None,
                 obsidian_vault: Path | None = None, skills_enabled: bool = True,
                 graphify_enabled: bool = True):
        self.home = home
        self.skills = None
        self.graph = None
        self.vault = None
        if skills_enabled:
            install_starters(home / "skills")
            self.skills = SkillLibrary(workspace=workspace, home=home)
        if graphify_enabled and workspace is not None:
            self.graph = GraphifyGraph(workspace)
        if obsidian_vault is not None:
            self.vault = ObsidianVault(obsidian_vault)

    def status(self) -> dict:
        catalog = self.skills.catalog() if self.skills else []
        graph_detected = bool(self.graph and self.graph.path.is_file() and not self.graph.path.is_symlink())
        return {
            "skills": {"enabled": self.skills is not None, "count": len(catalog),
                       "names": [s.name for s in catalog[:12]]},
            "graphify": {"enabled": self.graph is not None,
                         "export_detected": graph_detected,
                         "path": "graphify-out/graph.json" if self.graph else "",
                         "note": "Graph export is validated only when queried."},
            "obsidian": {"enabled": self.vault is not None,
                         "read_only": True,
                         "note": "Select an Obsidian vault folder and explicitly enable access."},
        }

    def definitions(self, prompt: str) -> list[dict]:
        """Conserve small-model context and plain-chat streaming where possible."""
        result = []
        if self.skills and _SKILL_TRIGGER.search(prompt):
            result.extend(SKILL_TOOLS)
        if self.vault and _VAULT_TRIGGER.search(prompt):
            result.extend(OBSIDIAN_TOOLS)
        if self.graph and self.graph.path.is_file() and _GRAPH_TRIGGER.search(prompt):
            result.extend(GRAPHIFY_TOOLS)
        return result

    @staticmethod
    def owns(name: str) -> bool:
        return name in ALL_TOOLS

    def call(self, name: str, args: dict, *, enabled: set[str]) -> dict:
        if name not in enabled or name not in ALL_TOOLS or not isinstance(args, dict):
            raise PermissionError("Intelligence tool is not enabled for this task")
        Draft202012Validator(ALL_TOOLS[name]["inputSchema"]).validate(args)
        if name == "star_skill_catalog":
            return self.skills.list()
        if name == "star_skill_load":
            return self.skills.load(args["name"])
        if name == "star_skill_reference":
            return self.skills.read_reference(args["name"], args["path"])
        if name == "star_obsidian_search":
            return self.vault.search(args["query"], limit=args.get("limit", 10))
        if name == "star_obsidian_read":
            return self.vault.read(args["path"])
        if name == "star_obsidian_list":
            return self.vault.list(limit=args.get("limit", 60))
        if name == "star_graphify_query":
            return self.graph.query(args["question"], limit=args.get("limit", 8))
        if name == "star_graphify_explain":
            return self.graph.explain(args["concept"])
        if name == "star_graphify_path":
            return self.graph.path_between(args["start"], args["end"])
        if name == "star_graphify_stats":
            return self.graph.stats()
        raise PermissionError("Unknown intelligence tool")


def for_settings(settings, home: Path) -> LocalIntelligence:
    """Construct a scoped hub without importing the desktop UI or its Qt stack."""
    workspace = Path(settings.workspace).expanduser() if settings.workspace else None
    obsidian = (Path(settings.obsidian_vault).expanduser()
                if settings.obsidian_enabled else None)
    return LocalIntelligence(
        home=home,
        workspace=workspace,
        obsidian_vault=obsidian,
        skills_enabled=settings.skills_enabled,
        graphify_enabled=settings.graphify_enabled,
    )
