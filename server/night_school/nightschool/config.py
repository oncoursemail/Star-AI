"""Settings of night school. Everything comes from the environment: no address, user name or key in the repository.
The defaults are the paths inside the STAR server container."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass
class Settings:
    home: Path = field(default_factory=lambda: Path(_env("STAR_NS_HOME", "/opt/star/learning")))
    brain_url: str = field(default_factory=lambda: _env("STAR_NS_BRAIN_URL", "http://127.0.0.1:8080"))
    key_file: str = field(default_factory=lambda: _env("STAR_NS_KEY_FILE", "/opt/star/secrets/api_keys"))
    model: str = field(default_factory=lambda: _env("STAR_NS_MODEL", "star-fast"))
    mode: str = field(default_factory=lambda: _env("STAR_NS_MODE", "auto"))
    # "" = the app's own default set of skill packs (STAR_SKILL_PACKS stays unset).
    packs: str = field(default_factory=lambda: _env("STAR_NS_PACKS", ""))
    luau_vm: str = field(default_factory=lambda: _env("STAR_NS_LUAU_VM", "/opt/star/bench/tools/luau/build/release/luau"))
    lock_dir: str = field(default_factory=lambda: _env("STAR_NS_LOCK_DIR", "/opt/star/lock"))
    # Politeness: the brain must have had no other client for idle_s seconds; never slot 0.
    idle_s: float = field(default_factory=lambda: float(_env("STAR_NS_IDLE_S", "600")))
    poll_s: float = field(default_factory=lambda: float(_env("STAR_NS_POLL_S", "10")))
    watch_s: float = field(default_factory=lambda: float(_env("STAR_NS_WATCH_S", "3")))
    slot: int = field(default_factory=lambda: int(_env("STAR_NS_SLOT", "1")))
    # STAR's resource planner (star/resource_planner_service.py) on this machine; "off" = only the idle gate above.
    # Planner down or without fresh data: the idle gate decides, exactly as before.
    planner_url: str = field(default_factory=lambda: _env("STAR_NS_PLANNER_URL", "http://127.0.0.1:8098"))
    # Learning rules.
    validation_percent: int = field(default_factory=lambda: int(_env("STAR_NS_VALIDATION_PERCENT", "20")))
    # W1 paired gate (star/eval_stats.py): 24 validation tasks, k samples per arm, both arms interleaved in one
    # session; only a significant improvement promotes, only a significant loss retires.
    validation_max: int = field(default_factory=lambda: int(_env("STAR_NS_VALIDATION_MAX", "24")))
    samples: int = field(default_factory=lambda: int(_env("STAR_NS_SAMPLES", "2")))
    recheck_samples: int = field(default_factory=lambda: int(_env("STAR_NS_RECHECK_SAMPLES", "2")))
    gate_alpha: float = field(default_factory=lambda: float(_env("STAR_NS_GATE_ALPHA", "0.05")))
    promote_fixes: int = field(default_factory=lambda: int(_env("STAR_NS_PROMOTE_FIXES", "2")))
    batch: int = field(default_factory=lambda: int(_env("STAR_NS_BATCH", "5")))
    recheck_every: int = field(default_factory=lambda: int(_env("STAR_NS_RECHECK_EVERY", "40")))
    retry_candidates: int = field(default_factory=lambda: int(_env("STAR_NS_RETRY_CANDIDATES", "1")))

    @property
    def app(self) -> Path:          # a copy of the repository (the folder that holds `star/`)
        return Path(_env("STAR_NS_APP", str(self.home / "app")))

    @property
    def pool(self) -> Path:
        return Path(_env("STAR_NS_POOL", str(self.home / "pool")))

    @property
    def data(self) -> Path:
        return self.home / "data"

    @property
    def report_file(self) -> Path:
        return self.home / "report" / "latest.md"

    @property
    def outbox(self) -> Path:
        return self.home / "outbox"

    @property
    def hold_file(self) -> Path:
        return self.data / "HOLD"

    def ensure_dirs(self) -> None:
        for path in (self.home, self.data, self.pool, self.outbox, self.report_file.parent):
            path.mkdir(parents=True, exist_ok=True)
