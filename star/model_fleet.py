"""Opt-in local llama.cpp model-fleet validation and non-destructive checks.

The server may route to multiple GGUF models, but STAR deliberately allows only
one *resident* router model on memory-constrained consumer hardware. No download,
shell, arbitrary remote endpoint, or automatic provider change is performed here.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .brain_router import validate_alias


@dataclass(frozen=True)
class FleetInventory:
    directory: Path
    weights: int
    projectors: int
    total_bytes: int


def inspect_models_dir(directory: Path) -> FleetInventory:
    """Inspect only the selected directory and its immediate model subfolders.

    Do not recursively traverse arbitrary user paths or symlinks. A folder
    without at least one real GGUF weight file cannot start the model router.
    """
    directory = Path(directory).expanduser()
    if directory.is_symlink():
        raise ValueError("Model directory cannot be a symlink")
    base = directory.resolve(strict=True)
    if not base.is_dir():
        raise ValueError("Choose an existing directory containing GGUF files")

    weights = projectors = total = 0

    def scan(folder: Path, *, allow_subfolders: bool) -> None:
        nonlocal weights, projectors, total
        for index, entry in enumerate(folder.iterdir()):
            if index >= 100:
                raise ValueError("Model directory has too many entries; choose a dedicated folder")
            if entry.is_symlink():
                raise ValueError("Model directory must not contain symlinks")
            if entry.is_dir():
                if allow_subfolders:
                    scan(entry, allow_subfolders=False)
                continue
            if not entry.is_file() or entry.suffix.lower() != ".gguf":
                continue
            size = entry.stat().st_size
            if size < 100_000:
                raise ValueError("GGUF file is too small or incomplete: " + entry.name[:80])
            if entry.name.lower().startswith("mmproj"):
                projectors += 1
            else:
                weights += 1
            total += size
            if weights + projectors > 40:
                raise ValueError("Too many GGUF files for a bounded model-fleet directory")

    scan(base, allow_subfolders=True)
    if weights < 1:
        raise ValueError("Model directory has no usable GGUF weights")
    return FleetInventory(base, weights, projectors, total)


def configured_models(settings) -> dict[str, str]:
    """Return model roles only when they have a configured ID."""
    roles = {
        "primary": settings.model,
        "fast": getattr(settings, "fast_model", ""),
        "reasoning": getattr(settings, "reasoning_model", ""),
        "roblox": getattr(settings, "roblox_model", ""),
        "vision": getattr(settings, "vision_model", ""),
    }
    for key, value in roles.items():
        validate_alias(value, field=key)
    return {key: value for key, value in roles.items() if value}


async def probe_model_team(client, settings, *, on_progress: Callable[[dict], None] | None = None,
                           per_model_timeout: float = 90.0) -> dict:
    """Probe each *unique* configured ID by real text completion, sequentially.

    Listing a model is insufficient; however, text success cannot establish
    vision or tool-calling support. Never make the model execute arbitrary code.
    """
    if not 1 <= per_model_timeout <= 180:
        raise ValueError("Invalid probe timeout")
    roles = configured_models(settings)
    if not roles:
        raise ValueError("Select a primary model before testing your model team")
    distinct = list(dict.fromkeys(roles.values()))
    observations: dict[str, dict] = {}
    for model_id in distinct:
        if on_progress:
            on_progress({"phase": "Testing a configured model", "model": model_id})
        try:
            result = await asyncio.wait_for(client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": "You are STAR. Return one brief sentence."},
                    {"role": "user", "content": "Reply with STAR ready."},
                ],
                max_tokens=128,
                temperature=0,
            ), timeout=per_model_timeout)
            choices = getattr(result, "choices", [])
            answer = str(choices[0].message.content or "").strip() if choices else ""
            if not answer:
                raise ValueError("Model did not return visible text")
            observations[model_id] = {"ok": True, "kind": "text_completion", "sample": answer[:120]}
        except Exception as exc:
            # Do not return arbitrary provider exception bodies, which may
            # include supplied URLs, headers or portions of private inputs.
            observations[model_id] = {"ok": False, "kind": "text_completion",
                                      "error_type": type(exc).__name__}
    return {
        "roles": {role: {"model": model_id, **observations[model_id]}
                  for role, model_id in roles.items()},
        "all_text_ready": all(x["ok"] for x in observations.values()),
        "note": "These are real text probes only. Vision, tool calls and Roblox Studio remain untested.",
    }


async def check_configured_team(settings, *, on_progress=None) -> dict:
    """Use only the selected provider/endpoint and its existing credentials."""
    from openai import AsyncOpenAI
    import httpx
    from .providers import connection_for

    settings.validate()
    endpoint, key = connection_for(settings)
    local = settings.provider == "local"
    async with AsyncOpenAI(base_url=endpoint, api_key=key,
                           timeout=httpx.Timeout(115 if local else 35, connect=8),
                           max_retries=0) as client:
        return await probe_model_team(client, settings, on_progress=on_progress,
                                      per_model_timeout=110 if local else 32)
