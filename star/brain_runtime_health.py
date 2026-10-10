"""Verify a real STAR Brain answer before committing model settings.

This function is deliberately independent of Qt so startup failure, rollback,
model-template rejection and multi-attempt readiness can be tested offline.
No fallback to a hosted provider or credential exposure is permitted.

When the owner has selected STAR Server (LAN), starting the on-device brain or
router only prepares a local fallback. It never switches the provider or the
model back to this PC.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
import time

import httpx

from .desktop_core import Settings, query_models
from .model_health import explain_model_failure, probe_chat_endpoint
from .providers import provider_kind


def _uses_server(settings) -> bool:
    """True when the saved provider is the LAN server (an unknown id is not)."""
    try:
        return provider_kind(settings) == "lan"
    except ValueError:
        return False


def start_verified_brain(
    runtime, info, settings_file: Path, app_home: Path, *,
    model_query=None, chat_probe=None, sleep=None, max_attempts: int = 70,
) -> dict:
    """Launch local llama.cpp and persist settings only after a text completion.

    Retry only transient HTTP readiness failures while the engine loads. If a
    freshly started engine fails, stop it; preserve the previous settings file.
    Existing processes are not forcibly stopped after a failed diagnostic.
    """
    if type(max_attempts) is not int or not 1 <= max_attempts <= 70:
        raise ValueError("Startup attempt budget must be 1–70")
    query = model_query or query_models
    probe = chat_probe or probe_chat_endpoint
    pause = sleep or time.sleep
    if runtime.router_running():
        raise RuntimeError("Stop the managed model router before starting the single-model Brain")
    launched = runtime.status() != "running"
    if launched:
        runtime.start(
            Path(info.executable), Path(info.model),
            Path(app_home) / "logs" / "star-brain-react.log",
            port=8080, context=4096, gpu_layers=30,
            projector=Path(info.projector),
        )
    try:
        endpoint = "http://127.0.0.1:8080/v1"
        model_probe = Settings(endpoint=endpoint)
        for attempt in range(max_attempts):
            if runtime.status() != "running":
                raise RuntimeError("STAR Brain stopped before becoming ready. Check local engine logs.")
            try:
                available = query(model_probe)
            except (httpx.HTTPError, OSError, TimeoutError, ConnectionError):
                available = []
            if available:
                # Build a candidate in memory. Do NOT save an unverified model,
                # overwrite an existing cloud provider or clobber chat settings.
                saved = Settings.load(Path(settings_file))
                keep_server = _uses_server(saved)
                # The readiness test always talks to the local engine itself,
                # even when STAR Server is the selected provider.
                candidate = replace(
                    saved, endpoint=endpoint, provider="local", model=str(available[0]),
                    llama_server=str(info.executable), gguf_model=str(info.model))
                try:
                    result = asyncio.run(probe(candidate))
                except Exception as error:
                    raise RuntimeError(
                        "STAR Brain started but failed its chat test: " +
                        explain_model_failure(error)
                    ) from error
                if not isinstance(result, dict) or not result.get("ok") or not str(result.get("sample", "")).strip():
                    raise RuntimeError("STAR Brain's completion test returned no visible answer")
                if keep_server:
                    # STAR Server stays selected with its own model. Record only
                    # where the verified local fallback lives.
                    chosen = replace(saved, endpoint=endpoint,
                                     llama_server=candidate.llama_server,
                                     gguf_model=candidate.gguf_model)
                else:
                    chosen = candidate
                chosen.save(Path(settings_file))
                return {
                    "model": candidate.model, "brain_running": True,
                    "chat_ready": True, "sample": str(result["sample"])[:180],
                    "provider": chosen.provider, "fallback_only": keep_server,
                }
            if attempt + 1 < max_attempts:
                pause(2)
        raise TimeoutError(
            "Local model did not become ready. Check STAR/logs/star-brain-react.log."
        )
    except Exception:
        if launched:
            runtime.stop()
        raise


def start_model_router(
    runtime, settings_file: Path, app_home: Path, executable: str, *,
    model_query=None, sleep=None, max_attempts: int = 35,
) -> dict:
    """Launch the managed GGUF router on loopback and record it without side effects.

    The router is an on-device feature, so it refuses to start unless the
    on-device provider is selected. Settings are re-read just before saving:
    if the owner picked STAR Server while the router was loading, the provider
    and model they chose are left exactly as they are.
    """
    if type(max_attempts) is not int or not 1 <= max_attempts <= 35:
        raise ValueError("Router startup attempt budget must be 1-35")
    query = model_query or query_models
    pause = sleep or time.sleep
    settings = Settings.load(Path(settings_file))
    settings.validate()
    if provider_kind(settings) == "lan":
        raise ValueError("The model router runs on this PC, and STAR Server manages its own models. "
                         "Select On-device as the provider to use the local router.")
    if provider_kind(settings) != "local":
        raise ValueError("Select Local as the inference provider")
    if not settings.router_models_dir:
        raise ValueError("Choose a local GGUF model folder first")
    if not executable:
        raise RuntimeError("Install the verified STAR Brain llama.cpp engine first")
    engine = Path(executable)
    runtime.start_router(engine, Path(settings.router_models_dir),
                         Path(app_home) / "logs" / "star-router-react.log", port=8080,
                         context=settings.router_context, gpu_layers=settings.gpu_layers)
    probe = Settings(endpoint="http://127.0.0.1:8080/v1")
    try:
        for attempt in range(max_attempts):
            if runtime.status() != "running":
                raise RuntimeError("Router exited; inspect STAR/logs/star-router-react.log")
            try:
                models = query(probe)
            except Exception:
                models = []
            if models:
                updated = Settings.load(Path(settings_file))
                updated.endpoint = probe.endpoint
                updated.llama_server = str(engine)
                if not _uses_server(updated):
                    updated.provider = "local"
                    if updated.model not in models:
                        updated.model = (updated.fast_model if updated.fast_model in models
                                         else models[0])
                updated.save(Path(settings_file))
                return {"brain_running": True, "model_router_running": True,
                        "model": updated.model, "models": models, "chat_ready": False,
                        "provider": updated.provider,
                        "note": "Router ready; actual model completion is not yet verified"}
            if attempt + 1 < max_attempts:
                pause(1)
        raise TimeoutError("Model router did not respond; check its log")
    except Exception:
        runtime.stop()
        raise
