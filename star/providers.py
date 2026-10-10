"""Strict provider routing and OS-backed credentials for STAR Intelligence.

Never accept a model-supplied base URL or store API tokens in settings/SQLite.
The desktop may use a named hosted model only after the owner configures a key.
"""
from __future__ import annotations
from dataclasses import dataclass
import os

SERVICE = "STAR Intelligence"

@dataclass(frozen=True)
class Provider:
    label: str
    base_url: str
    env_var: str
    suggested_model: str

PROVIDERS: dict[str, Provider] = {
    "groq": Provider("GroqCloud", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-20b"),
    "openrouter": Provider("OpenRouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "openrouter/free"),
    "gemini": Provider("Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY", "gemini-2.5-flash-lite"),
    "cerebras": Provider("Cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "gpt-oss-120b"),
}
SEARCH_KEYS = {"brave": "BRAVE_SEARCH_API_KEY", "tavily": "TAVILY_API_KEY"}
KEY_ENV = {**{name: provider.env_var for name, provider in PROVIDERS.items()}, **SEARCH_KEYS}

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
    if settings.provider == "local":
        return settings.endpoint, "local-only"
    if settings.provider not in PROVIDERS:
        raise ValueError("Unrecognized model provider")
    key = get_api_key(settings.provider)
    if not key:
        raise ValueError(f"{PROVIDERS[settings.provider].label} needs an API key. Add it in Settings → AI providers.")
    return PROVIDERS[settings.provider].base_url, key

def provider_catalog() -> list[dict]:
    statuses = credential_status()
    return [{"id": "local", "label": "On-device (private)", "model": "", "connected": True}] + [
        {"id": name, "label": p.label, "model": p.suggested_model, "connected": statuses[name]}
        for name, p in PROVIDERS.items()
    ]
