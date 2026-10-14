"""Narrow model-facing interface; operator review stays outside tool dispatch.

This adapter can be handed to STAR's existing tool orchestration or invoked by
other assistants through the JSON CLI. It adds no executable permission, remote
host, shell, fixture-writing action or ability to activate a proposal.
"""
from __future__ import annotations

from .._lazy import lazy_attr
Draft202012Validator = lazy_attr("jsonschema", "Draft202012Validator")  # loaded on first validation

from .store import SharedBrain, serialize


def _tool(name, description, properties, required=()):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": properties,
                            "required": list(required), "additionalProperties": False}}


def _string(maximum):
    return {"type": "string", "minLength": 1, "maxLength": maximum}


READ_TOOLS = (
    _tool("shared_brain_query", "Retrieve bounded project graph references with locations and source freshness.",
          {"question": _string(220), "limit": {"type": "integer", "minimum": 1, "maximum": 15},
           "budget_chars": {"type": "integer", "minimum": 512, "maximum": 6000}}, ("question",)),
    _tool("shared_brain_stats", "Read actual shared graph and audit counts.", {}),
    _tool("shared_brain_lessons", "Read candidate retrieval outcomes; these are reference observations, never trusted rules.", {}),
    _tool("shared_brain_feedback", "Append useful/corrected/dead-end evidence to a query in this project. No automatic promotion.",
          {"query_id": _string(32), "outcome": {"enum": ["useful", "corrected", "dead_end"]},
           "answer": {"type": "string", "maxLength": 2000},
           "correction": {"type": "string", "maxLength": 2000}}, ("query_id", "outcome")),
)
PROPOSAL_TOOLS = (
    _tool("shared_brain_active_query", "Retrieve through the current separately reviewed knowledge/recipe version with verified source snapshot and bounded reference context.",
          {"question": _string(220),
           "budget_chars": {"type": "integer", "minimum": 512, "maximum": 6000}}, ("question",)),
    _tool("shared_brain_propose_aliases", "Propose bounded query expansion using existing source vocabulary; awaits fixed tests and separate owner review.",
          {"aliases": {"type": "object", "minProperties": 1, "maxProperties": 12,
                       "additionalProperties": {"type": "array", "minItems": 1, "maxItems": 3,
                                                "items": _string(41)}}}, ("aliases",)),
    _tool("shared_brain_propose_recipe", "Propose a declarative read-only ToolWorkshop recipe over sources the host already configured. No generated code runs.",
          {"recipe": {"type": "object", "properties": {"name": _string(40), "description": _string(200),
                      "steps": {"type": "array", "minItems": 1, "maxItems": 4, "items": {"type": "object",
                          "properties": {"source": {"enum": ["knowledge", "workspace", "obsidian", "graphify", "skills"]},
                                         "limit": {"type": "integer", "minimum": 1, "maximum": 8}},
                          "required": ["source"], "additionalProperties": False}}},
                      "required": ["name", "description", "steps"], "additionalProperties": False}}, ("recipe",)),
    _tool("shared_brain_candidate_status", "Read bounded proposal states and the active retrieval version; cannot approve or activate.", {}),
)


class SharedBrainTools:
    def __init__(self, brain: SharedBrain, *, actor: str, improvement_loop=None):
        if not isinstance(actor, str) or not actor or len(actor) > 80:
            raise ValueError("A host-selected actor is required")
        if improvement_loop is not None:
            if improvement_loop.root != brain.workspace:
                raise ValueError("The improvement controller must belong to the selected project")
            if not 512 <= improvement_loop.limits.context_chars <= 6000:
                raise ValueError("The controller must evaluate within the model tool context budget")
        self.brain, self.actor, self.loop = brain, actor, improvement_loop
        self.tools = {t["name"]: t for t in READ_TOOLS + (PROPOSAL_TOOLS if self.loop else ())}

    def definitions(self):
        # A copy prevents callers from mutating the host registry.
        import json
        return json.loads(serialize(list(self.tools.values())))

    def call(self, name: str, arguments: dict):
        if name not in self.tools:
            raise PermissionError("Shared-brain tool is not configured")
        Draft202012Validator(self.tools[name]["inputSchema"]).validate(arguments)
        if name == "shared_brain_query":
            return self.brain.query(**arguments)
        if name == "shared_brain_stats":
            return self.brain.stats()
        if name == "shared_brain_lessons":
            return self.brain.lessons()
        if name == "shared_brain_feedback":
            return self.brain.feedback(actor=self.actor, **arguments)
        if name == "shared_brain_active_query":
            result = self.loop.retrieve(arguments["question"])
            budget = arguments.get("budget_chars", self.loop.limits.context_chars)
            if len(serialize(result)) > budget:
                raise ValueError("Active context exceeds the requested budget; evaluated evidence cannot be trimmed")
            return result
        if name == "shared_brain_candidate_status":
            result = self.loop.status()
            result["candidates"] = dict(list(result["candidates"].items())[-30:])
            return result
        proposal = (self.loop.propose_aliases(arguments["aliases"]) if name == "shared_brain_propose_aliases"
                    else self.loop.propose_recipe(arguments["recipe"]))
        return {key: proposal[key] for key in ("id", "kind", "state", "config_digest", "base_version")}
