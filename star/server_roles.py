"""Which STAR Server model does which job.

A STAR Server may offer a fleet of models behind one address. STAR asks the
server what it offers (its `/v1/models` list, read once at "Test server" and
once at warm-up) and maps four jobs to it:

  quick   short chat: no tools, no image, nothing about Roblox or code
  code    Roblox/Luau questions, coding, tool use, Agent mode
  vision  a message with an image
  deep    the slow best-quality model, only when the owner asks for it

What this module never does:

  * It never writes a setting. A role field the owner filled in by hand
    (`fast_model`, `reasoning_model`, `roblox_model`, `vision_model`) always
    wins; a discovered model only fills a blank one, for the running process.
  * It never touches a cloud provider or the on-PC brain: `effective()`
    returns their settings unchanged.
  * It never asks the server about a model that is not loaded. On a llama.cpp
    router `GET /props?model=X` LOADS X, so limits are only read for models the
    list reports as loaded.

A role whose model is missing, or failed when it was used, is simply absent, and
`brain_router.select_route` falls back to the single configured model.
"""
from __future__ import annotations

from dataclasses import dataclass, replace, is_dataclass
import copy
import re

from .providers import (remember_model_names, remember_server_limits, uses_star_server)

# Names a STAR Server gives its models (docs/research/server-inference.md, 4.3).
# The first name the server offers wins; a name may be a model id or an alias.
ROLE_NAMES: dict[str, tuple[str, ...]] = {
    "quick": ("star-voice", "star-quick"),
    "code": ("star-fast", "star-code"),
    "vision": ("star-vision",),
    "deep": ("star-deep",),
}
# The settings field each discovered role fills when the owner left it blank.
# `deep` has no field on purpose: nothing routes to it automatically.
ROLE_FIELDS: dict[str, str] = {
    "fast_model": "quick", "reasoning_model": "code", "roblox_model": "code", "vision_model": "vision",
}
ROLE_LABELS = {"quick": "Quick chat", "code": "Roblox, code and tools", "vision": "Images",
               "deep": "Best quality (slow, on request)"}
_NAME = re.compile(r"[^\s\x00-\x1f\x7f]{1,180}")


@dataclass(frozen=True)
class Offered:
    """One entry of the server's model list."""
    id: str
    aliases: tuple[str, ...] = ()
    loaded: bool = True       # False: listed, but answering would first load it
    failed: bool = False      # the server tried to load it and could not
    images: bool | None = None  # None: the server did not say

    @property
    def names(self) -> tuple[str, ...]:
        return (self.id, *self.aliases)


def parse_models(listed) -> list[Offered]:
    """The `data` array of `/v1/models` -> entries. Unknown shapes are skipped, never an error."""
    found: list[Offered] = []
    for item in listed if isinstance(listed, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not _NAME.fullmatch(item["id"]):
            continue
        aliases = tuple(alias for alias in item.get("aliases") or []
                        if isinstance(alias, str) and _NAME.fullmatch(alias))[:8]
        status = item.get("status") if isinstance(item.get("status"), dict) else {}
        state = status.get("value")
        inputs = (item.get("architecture") or {}).get("input_modalities") \
            if isinstance(item.get("architecture"), dict) else None
        found.append(Offered(
            id=item["id"], aliases=aliases,
            # A plain llama-server (no router) has no status: the model it lists is the loaded one.
            loaded=state in (None, "loaded"),
            failed=bool(status.get("failed")) or state == "failed",
            images=("image" in inputs) if isinstance(inputs, list) else None))
    return found[:100]


def map_roles(offered) -> dict[str, str]:
    """The role table: {role: the name to request}. Pure; first offered name wins."""
    by_name: dict[str, Offered] = {}
    for model in offered:
        if not model.failed:
            for name in model.names:
                by_name.setdefault(name, model)
    roles: dict[str, str] = {}
    for role, names in ROLE_NAMES.items():
        name = next((name for name in names if name in by_name), "")
        if name:
            roles[role] = name
    if "vision" in roles and by_name[roles["vision"]].images is False:
        del roles["vision"]          # the name is offered, but the server says it cannot read images
    if "vision" not in roles and "code" in roles and by_name[roles["code"]].images:
        roles["vision"] = roles["code"]
    return roles


# Per server address: what was last discovered. Process memory only, no secrets.
_FLEETS: dict[str, dict] = {}


def _endpoint(settings) -> str:
    return str(getattr(settings, "server_endpoint", "")).rstrip("/")


def remember_models(endpoint: str, listed) -> dict[str, str]:
    """Record a server's model list (already fetched by the caller) and return its role table."""
    endpoint = str(endpoint).rstrip("/")
    offered = parse_models(listed)
    for model in offered:
        remember_model_names(endpoint, model.id, model.aliases)
    roles = map_roles(offered)
    _FLEETS[endpoint] = {
        "roles": roles,
        "loaded": {name for model in offered if model.loaded and not model.failed for name in model.names},
        "ids": {name: model.id for model in offered for name in model.names},
    }
    return dict(roles)


def known(endpoint: str) -> bool:
    """Has this server's model list been read in this process?"""
    return str(endpoint).rstrip("/") in _FLEETS


def discover(endpoint: str, key: str, *, transport=None, timeout: float = 5.0) -> dict[str, str]:
    """Ask a server once which models it offers and remember the answer. {} when it does not answer.

    For callers that have not run the full server check (a voice call started before the
    warm-up). One GET of `/v1/models`, plus `/props` for the loaded role models only.
    """
    import httpx
    endpoint = str(endpoint).rstrip("/")
    auth = {"Authorization": f"Bearer {key}"}
    try:
        # trust_env=False: a system proxy must never see LAN traffic or the key.
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=min(timeout, 5.0)), trust_env=False,
                          follow_redirects=False, transport=transport) as client:
            answer = client.get(endpoint + "/models", headers=auth)
            if answer.status_code != 200:
                return {}
            roles = remember_models(endpoint, answer.json().get("data", []))
            read_limits(client, endpoint[:-len("/v1")] if endpoint.endswith("/v1") else endpoint, endpoint, auth)
            return roles
    except (httpx.HTTPError, ValueError, AttributeError):
        return {}


def forget(endpoint: str = "") -> None:
    """Drop what was discovered (one address, or everything). Used by tests and when the address changes."""
    if endpoint:
        _FLEETS.pop(str(endpoint).rstrip("/"), None)
    else:
        _FLEETS.clear()


def discovered_roles(settings) -> dict[str, str]:
    """{role: model name} for the selected STAR Server; {} for anything else or before discovery."""
    if not uses_star_server(settings):
        return {}
    return dict(_FLEETS.get(_endpoint(settings), {}).get("roles", {}))


def loaded_role_models(endpoint: str) -> list[str]:
    """Role models that are loaded right now: the only ones whose /props may be asked."""
    fleet = _FLEETS.get(str(endpoint).rstrip("/"), {})
    seen: set[str] = set()
    result: list[str] = []
    for name in fleet.get("roles", {}).values():
        model_id = fleet["ids"].get(name, name)
        if name in fleet.get("loaded", ()) and model_id not in seen:   # one question per loaded model
            seen.add(model_id)
            result.append(name)
    return result


def same_model(endpoint: str, first: str, second: str) -> bool:
    """Do two names reach the same model on this server (`star-vision` and `star-fast`)?"""
    ids = _FLEETS.get(str(endpoint).rstrip("/"), {}).get("ids", {})
    return ids.get(first, first) == ids.get(second, second)


def mark_failed(settings, model: str) -> None:
    """A routed model could not be used: stop routing to it until the server is asked again."""
    fleet = _FLEETS.get(_endpoint(settings))
    if fleet:
        model_id = fleet["ids"].get(model, model)
        fleet["roles"] = {role: name for role, name in fleet["roles"].items()
                          if fleet["ids"].get(name, name) != model_id}


def effective(settings):
    """`settings` with blank role fields filled from the server's fleet. Never saved.

    Returns the very same object for a cloud provider, the on-PC brain, or a
    server that has not been asked yet, so those paths are untouched.
    """
    roles = discovered_roles(settings)
    fill = {field: roles[role] for field, role in ROLE_FIELDS.items()
            if role in roles and not str(getattr(settings, field, "") or "").strip()}
    if not fill:
        return settings
    if is_dataclass(settings) and not isinstance(settings, type):
        return replace(settings, **fill)
    clone = copy.copy(settings)
    for field, value in fill.items():
        setattr(clone, field, value)
    return clone


def deep_model(settings) -> str:
    """The slow best-quality model, or '' when the server does not offer one."""
    return discovered_roles(settings).get("deep", "")


def quick_model(settings, default: str = "") -> str:
    """The model for short spoken or typed chat: the owner's choice, else the server's quick model."""
    by_hand = str(getattr(settings, "fast_model", "") or "").strip()
    if by_hand:
        return by_hand
    roles = _FLEETS.get(_endpoint(settings), {}).get("roles", {})
    return roles.get("quick") or str(getattr(settings, "model", "") or "").strip() or default


def role_report(settings) -> list[dict]:
    """For the interface: every role, the model it uses and who chose it. No address, no key."""
    roles = discovered_roles(settings)
    primary = str(getattr(settings, "model", "") or "")
    by_hand = {role: str(getattr(settings, field, "") or "")
               for field, role in ROLE_FIELDS.items() if field != "roblox_model"}
    report = []
    for role, label in ROLE_LABELS.items():
        if by_hand.get(role):
            model, source = by_hand[role], "manual"
        elif role in roles:
            model, source = roles[role], "server"
        elif role == "deep":
            continue                      # not offered: nothing to show
        else:
            model, source = primary, "default"
        report.append({"role": role, "label": label, "model": model[:180], "source": source})
    return report


def read_limits(client, root: str, endpoint: str, auth: dict, *, skip: str = "") -> None:
    """Ask `/props` for each loaded role model so its slot count and context are known.

    `client` is the caller's httpx client. Models that are not loaded are never
    asked (it would load them). Failures are ignored: limits are informational.
    """
    for name in loaded_role_models(endpoint):
        if skip and same_model(endpoint, name, skip):
            continue                      # the caller already asked about this one
        try:
            answer = client.get(root + "/props", params={"model": name}, headers=auth)
            facts = answer.json() if answer.status_code == 200 else {}
            context = (facts.get("default_generation_settings") or {}).get("n_ctx")
            slots = facts.get("total_slots")
        except Exception:
            continue
        if type(context) is int and context > 0:
            remember_server_limits(endpoint, name, context, slots if type(slots) is int and slots > 0 else 1)
