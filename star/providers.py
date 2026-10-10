"""Strict provider routing and OS-backed credentials for STAR Intelligence.

Never accept a model-supplied base URL or store API tokens in settings/SQLite.
The desktop may use a named hosted model only after the owner configures a key.

Every provider has a typed kind, and callers branch on the kind, never on the id:

  local  the managed llama.cpp brain on this PC's loopback interface (no key)
  lan    STAR Server: an owner-entered private address on the local network,
         OpenAI-compatible, always with an API key
  cloud  a fixed HTTPS vendor with the owner's own key

The LAN address is typed by the owner in Settings. It is validated here, at the
one place every model call passes through, so the server key can only ever be
sent to a private IP literal.
"""
from __future__ import annotations
from dataclasses import dataclass
import ipaddress
import os
from typing import Literal
from urllib.parse import urlsplit

SERVICE = "STAR Intelligence"
ProviderKind = Literal["local", "lan", "cloud"]

@dataclass(frozen=True)
class Provider:
    label: str
    base_url: str
    env_var: str
    suggested_model: str
    kind: ProviderKind = "cloud"
    base_url_from_settings: bool = False  # the owner's Settings hold the address
    requires_key: bool = True
    default_timeout: float = 55.0         # seconds of silence before one request is dropped
    allow_parallel: bool = True           # may STAR issue two model calls at once?

PROVIDERS: dict[str, Provider] = {
    "groq": Provider("GroqCloud", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-20b"),
    "openrouter": Provider("OpenRouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "openrouter/free"),
    "gemini": Provider("Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY", "gemini-2.5-flash-lite"),
    "cerebras": Provider("Cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "gpt-oss-120b"),
}
LOCAL = "local"
STAR_SERVER = "star_server"
# Private providers never leave the owner's machines. Their address comes from
# Settings (loopback for local, a validated private IP for the LAN server).
PRIVATE_PROVIDERS: dict[str, Provider] = {
    LOCAL: Provider("On-device (private)", "", "", "", kind="local",
                    base_url_from_settings=True, requires_key=False,
                    default_timeout=95.0, allow_parallel=False),
    STAR_SERVER: Provider("STAR Server (LAN)", "", "STAR_SERVER_API_KEY", "", kind="lan",
                          base_url_from_settings=True, requires_key=True,
                          default_timeout=600.0, allow_parallel=True),
}
ALL_PROVIDERS: dict[str, Provider] = {**PRIVATE_PROVIDERS, **PROVIDERS}
SEARCH_KEYS = {"brave": "BRAVE_SEARCH_API_KEY", "tavily": "TAVILY_API_KEY"}
KEY_ENV = {**{name: provider.env_var for name, provider in ALL_PROVIDERS.items()
              if provider.requires_key}, **SEARCH_KEYS}

# RFC 1918, loopback and link-local only. `ipaddress.is_private` is wider than
# this (it also accepts 0.0.0.0/8, documentation ranges and 240.0.0.0/4).
_LAN_NETWORKS = tuple(ipaddress.ip_network(block) for block in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",   # RFC 1918 private
    "127.0.0.0/8", "169.254.0.0/16",                   # loopback, link-local
    "::1/128", "fc00::/7", "fe80::/10",                # IPv6 loopback, ULA, link-local
))
_LAN_HINT = "Use your server's private IP address, for example http://192.168.1.20:8080/v1"

def validate_lan_endpoint(value) -> str:
    """Return the canonical private `scheme://ip:port/v1` URL, or raise ValueError.

    Fail closed: an IP literal only (no hostnames, so DNS cannot redirect the
    key), a private/loopback/link-local address, an explicit unprivileged port,
    the exact path /v1, and no credentials, query or fragment.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Enter your STAR Server address. " + _LAN_HINT)
    if len(value) > 200 or any(ch.isspace() or ord(ch) < 33 or ord(ch) == 127 for ch in value):
        raise ValueError("STAR Server address contains spaces or control characters")
    if any(ch in value for ch in "@?#%\\"):
        raise ValueError("STAR Server address must not contain credentials, a query, a fragment or % escapes")
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError as exc:
        raise ValueError("STAR Server address is not a valid URL. " + _LAN_HINT) from exc
    if url.scheme not in ("http", "https"):
        raise ValueError("STAR Server address must start with http:// or https://")
    if url.username is not None or url.password is not None or url.query or url.fragment:
        raise ValueError("STAR Server address must not contain credentials, a query or a fragment")
    try:
        address = ipaddress.ip_address(url.hostname or "")
    except ValueError as exc:
        raise ValueError("STAR Server address must use an IP address, not a host name. " + _LAN_HINT) from exc
    if not any(address in network for network in _LAN_NETWORKS):
        raise ValueError("STAR Server must be on your private network (10.x, 172.16-31.x, 192.168.x, "
                         "127.x or link-local). Public addresses are refused.")
    if port is None or not 1024 <= port <= 65535:
        raise ValueError("STAR Server address needs a port from 1024 to 65535, for example :8080")
    host = f"[{address.compressed}]" if address.version == 6 else address.compressed
    canonical = f"{url.scheme}://{host}:{port}/v1"
    # What was validated must be exactly what is used: no odd encodings, extra
    # path segments, leading zeros or anything urlsplit silently normalised.
    if value not in (canonical, canonical + "/"):
        raise ValueError(f"STAR Server address must look exactly like {canonical}")
    return canonical

def provider_spec(name) -> Provider:
    """Typed metadata for a provider id. Unknown ids fail closed."""
    spec = ALL_PROVIDERS.get(name) if isinstance(name, str) else None
    if spec is None:
        raise ValueError("Unrecognized model provider")
    return spec

def provider_kind(settings) -> ProviderKind:
    """`local`, `lan` or `cloud` for the selected provider. Compare this, not the id."""
    return provider_spec(getattr(settings, "provider", LOCAL)).kind

def uses_star_server(settings) -> bool:
    """True when STAR Server (LAN) is the selected provider. Never raises, even
    for a hand-edited settings file with an unknown provider id."""
    try:
        return provider_kind(settings) == "lan"
    except ValueError:
        return False

@dataclass(frozen=True)
class CallLimits:
    request_timeout: float   # seconds without a byte before one model request is dropped
    connect_timeout: float
    parallel: int            # simultaneous model calls STAR may issue (1 or 2)
    trust_env: bool          # False: private traffic never goes through a system proxy

def call_limits(settings) -> CallLimits:
    """Per-provider HTTP budget. The LAN server is a slow CPU box: be generous."""
    spec = provider_spec(getattr(settings, "provider", LOCAL))
    if spec.kind == "lan":
        slots = getattr(settings, "server_parallel", 1)
        return CallLimits(float(getattr(settings, "server_timeout", spec.default_timeout)), 5.0,
                          max(1, min(2, slots if type(slots) is int else 1)), False)
    return CallLimits(spec.default_timeout, 8.0, 2 if spec.allow_parallel else 1, True)

def _check_name(name: str) -> None:
    if name not in KEY_ENV:
        raise ValueError("Unknown credential provider")

def get_api_key(name: str) -> str | None:
    """Environment variables take precedence; keyring is optional for CLI tests."""
    _check_name(name)
    value = os.environ.get(KEY_ENV[name], "").strip()
    if value:
        return value
    try:
        import keyring
        return (keyring.get_password(SERVICE, name) or "").strip() or None
    except Exception:
        return None

def save_api_key(name: str, token: str) -> None:
    _check_name(name)
    if not isinstance(token, str) or not 8 <= len(token) <= 2048 or any(c.isspace() for c in token):
        raise ValueError("Paste a valid API key (8–2048 characters, no spaces)")
    try:
        import keyring
        keyring.set_password(SERVICE, name, token)
    except Exception as exc:
        raise RuntimeError("Secure Windows credential storage unavailable; configure the environment variable instead") from exc

def clear_api_key(name: str) -> None:
    _check_name(name)
    try:
        import keyring
        keyring.delete_password(SERVICE, name)
    except Exception:
        pass

def credential_status() -> dict[str, bool]:
    """Never return key bytes to the browser or model."""
    return {name: bool(get_api_key(name)) for name in KEY_ENV}

def connection_for(settings) -> tuple[str, str]:
    """The single place that decides which address and bearer a model call uses."""
    spec = provider_spec(getattr(settings, "provider", None))
    if spec.kind == "local":
        return settings.endpoint, "local-only"
    if spec.kind == "lan":
        endpoint = validate_lan_endpoint(getattr(settings, "server_endpoint", ""))
        key = get_api_key(STAR_SERVER)
        if not key:
            raise ValueError("STAR Server needs its API key. Add it in Settings → STAR Server.")
        return endpoint, key
    key = get_api_key(settings.provider)
    if not key:
        raise ValueError(f"{spec.label} needs an API key. Add it in Settings → AI providers.")
    return spec.base_url, key

def open_client(settings, *, request_timeout: float | None = None):
    """Build the AsyncOpenAI client for the selected provider with its own limits.

    A private LAN server gets an explicit httpx client with `trust_env=False`,
    so a Windows system proxy can never see the prompt or the server key.
    """
    from openai import AsyncOpenAI
    import httpx
    endpoint, key = connection_for(settings)
    limits = call_limits(settings)
    timeout = httpx.Timeout(request_timeout or limits.request_timeout, connect=limits.connect_timeout)
    extra = {} if limits.trust_env else {
        "http_client": httpx.AsyncClient(trust_env=False, timeout=timeout)}
    return AsyncOpenAI(base_url=endpoint, api_key=key, timeout=timeout, max_retries=0, **extra)

# Context size and slot count last reported by a server's own /props endpoint.
# Process memory only: nothing here is a secret and nothing is written to disk.
_SERVER_LIMITS: dict[tuple[str, str], tuple[int, int]] = {}

def remember_server_limits(endpoint: str, model: str, context_tokens: int, slots: int) -> None:
    if type(context_tokens) is int and context_tokens > 0:
        _SERVER_LIMITS[(endpoint, model)] = (context_tokens, slots if type(slots) is int and slots > 0 else 1)

def server_context_tokens(settings) -> int:
    """Per-request context of the LAN model: the owner's value, else what /props last said, else 0."""
    chosen = getattr(settings, "server_context_tokens", 0)
    if type(chosen) is int and chosen > 0:
        return chosen
    known = _SERVER_LIMITS.get((str(getattr(settings, "server_endpoint", "")).rstrip("/"),
                                str(getattr(settings, "model", ""))))
    return known[0] if known else 0

def provider_catalog() -> list[dict]:
    statuses = credential_status()
    return [{"id": LOCAL, "label": PRIVATE_PROVIDERS[LOCAL].label, "model": "", "connected": True, "kind": "local"},
            {"id": STAR_SERVER, "label": PRIVATE_PROVIDERS[STAR_SERVER].label, "model": "",
             "connected": statuses[STAR_SERVER], "kind": "lan"}] + [
        {"id": name, "label": p.label, "model": p.suggested_model, "connected": statuses[name], "kind": p.kind}
        for name, p in PROVIDERS.items()
    ]
