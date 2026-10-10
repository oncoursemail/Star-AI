"""Verify a real STAR Brain answer before committing model settings.

This function is deliberately independent of Qt so startup failure, rollback,
model-template rejection and multi-attempt readiness can be tested offline.
No fallback to a hosted provider or credential exposure is permitted.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import time

import httpx

from .desktop_core import Settings, query_models
from .model_health import explain_model_failure, probe_chat_endpoint


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
                candidate = Settings.load(Path(settings_file))
                candidate.endpoint = endpoint
                candidate.provider = "local"
                candidate.model = str(available[0])
                candidate.llama_server = str(info.executable)
                candidate.gguf_model = str(info.model)
                try:
                    result = asyncio.run(probe(candidate))
                except Exception as error:
                    raise RuntimeError(
                        "STAR Brain started but failed its chat test: " +
                        explain_model_failure(error)
                    ) from error
                if not isinstance(result, dict) or not result.get("ok") or not str(result.get("sample", "")).strip():
                    raise RuntimeError("STAR Brain's completion test returned no visible answer")
                candidate.save(Path(settings_file))
                return {
                    "model": candidate.model, "brain_running": True,
                    "chat_ready": True, "sample": str(result["sample"])[:180],
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
