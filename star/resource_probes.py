"""Cheap load probes for the resource planner (stdlib only, read-only, no key or address is ever printed).

* Linux machines (brain 1, brain 2): /proc/stat (CPU busy share between two looks), /proc/meminfo (MemAvailable),
  the quiet lock directory (/opt/star/lock, stale after 15 minutes, never removed here), Studio processes (brain 2).
* The STAR Brain (llama.cpp router, brain 1): `GET /v1/models` lists the models; ONLY models whose status is
  "loaded" are then asked `GET /slots?model=` and `GET /metrics?model=`. Asking an unloaded model makes the router
  LOAD it (23 GB for star-deep: seen 2026-10-13, brain-performance notes), so that is never done.
* Windows PC: GlobalMemoryStatusEx, GetSystemTimes, `nvidia-smi --query-gpu`, and whether the owner is busy
  (a known game process, a fullscreen foreground window, or a graphics load on the GPU that no compute process
  explains). Each probe returns None/"" on failure: an unknown is never reported as "free".
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Callable
import urllib.error
import urllib.request

LOCK_DIR = os.environ.get("STAR_LOCK_DIR", "/opt/star/lock")
LOCK_STALE_S = 900
DEFAULT_GAMES = ("RobloxPlayerBeta.exe", "FortniteClient-Win64-Shipping.exe", "VALORANT-Win64-Shipping.exe",
                 "cs2.exe", "GTA5.exe", "Minecraft.Windows.exe", "javaw.exe", "r5apex.exe", "RocketLeague.exe",
                 "eldenring.exe", "Overwatch.exe", "LeagueClient.exe", "League of Legends.exe")


# --- Linux ---------------------------------------------------------------------------------------------------------

def proc_cpu_times(path: str = "/proc/stat") -> tuple[int, int] | None:
    """(busy, total) jiffies of all CPUs, or None."""
    try:
        with open(path, encoding="ascii") as handle:
            first = handle.readline().split()
    except OSError:
        return None
    if not first or first[0] != "cpu":
        return None
    values = [int(x) for x in first[1:9] if x.isdigit()]
    if len(values) < 4:
        return None
    idle = values[3] + (values[4] if len(values) > 4 else 0)     # idle + iowait
    return sum(values) - idle, sum(values)


def cpu_busy_share(before: tuple[int, int] | None, after: tuple[int, int] | None) -> float | None:
    if not before or not after or after[1] <= before[1]:
        return None
    return max(0.0, min(1.0, (after[0] - before[0]) / (after[1] - before[1])))


def proc_meminfo(path: str = "/proc/meminfo") -> tuple[int, int] | None:
    """(total MiB, available MiB), or None."""
    found = {}
    try:
        with open(path, encoding="ascii") as handle:
            for line in handle:
                key, _, rest = line.partition(":")
                if key in ("MemTotal", "MemAvailable"):
                    found[key] = int(rest.split()[0]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    if "MemTotal" not in found or "MemAvailable" not in found:
        return None
    return found["MemTotal"], found["MemAvailable"]


def cgroup_memory_limit_mib(path: str = "/sys/fs/cgroup/memory.max") -> int | None:
    try:
        text = Path(path).read_text(encoding="ascii").strip()
    except OSError:
        return None
    return int(text) // 2**20 if text.isdigit() else None


def lock_owner(lock_dir: str = LOCK_DIR, *, stale_s: float = LOCK_STALE_S, clock=time.time) -> str:
    """Owner of a fresh quiet lock, "" when there is none or it is stale (same rule as server/knowledge/starkb/quiet.py:
    the newest of the directory and its owner file counts)."""
    base = Path(lock_dir)
    try:
        newest = base.stat().st_mtime
    except OSError:
        return ""
    owner = "unknown"
    try:
        newest = max(newest, (base / "owner").stat().st_mtime)
        words = (base / "owner").read_text(encoding="utf-8", errors="replace").split()
        if words:
            owner = re.sub(r"[^A-Za-z0-9_.-]", "", words[0])[:40] or "unknown"
    except OSError:
        pass
    return owner if clock() - newest < stale_s else ""


def studio_processes(proc: str = "/proc") -> list[dict]:
    """Roblox Studio processes (brain 2 runs it under Vinegar/Wine). The place in the launch line is NOT a verified
    identity; the Studio connector checks that at dispatch."""
    found = []
    try:
        entries = [e for e in os.listdir(proc) if e.isdigit()]
    except OSError:
        return found
    for pid in entries:
        try:
            raw = Path(proc, pid, "cmdline").read_bytes()[:4096]
        except OSError:
            continue
        line = raw.replace(b"\0", b" ").decode("utf-8", "replace")
        if "RobloxStudioBeta.exe" not in line or "CrashHandler" in line:
            continue
        place = re.search(r"placeId:(\d+)", line)
        universe = re.search(r"universeId:(\d+)", line)
        found.append({"studio_id": f"studio-{pid}",
                      "place_id": int(place.group(1)) if place else 0,
                      "universe_id": int(universe.group(1)) if universe else 0})
    return found[:8]


# --- the STAR Brain (llama.cpp router) -------------------------------------------------------------------------------

def read_key(key_file: str) -> str:
    """The first non-comment line of a key file, kept in memory only."""
    try:
        for line in Path(os.path.expanduser(key_file)).read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.strip().startswith("#"):
                return line.strip()
    except OSError:
        pass
    return ""


class BrainProbe:
    """Slots and queues of the loaded models. `fetch(path) -> bytes` can be handed in for tests."""

    def __init__(self, url: str = "http://127.0.0.1:8080", key: str = "", *, timeout: float = 3.0,
                 fetch: Callable[[str], bytes] | None = None):
        self._url, self._key, self._timeout = url.rstrip("/"), key, timeout
        self._fetch = fetch or self._http

    def _http(self, path: str) -> bytes:
        request = urllib.request.Request(self._url + path)
        if self._key:
            request.add_header("Authorization", "Bearer " + self._key)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as reply:
                return reply.read(4 * 1024 * 1024)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            raise OSError(type(exc).__name__) from None          # the text may hold the address

    def loaded_models(self) -> list[str]:
        data = json.loads(self._fetch("/v1/models").decode("utf-8", "replace"))
        names = []
        for row in (data.get("data") or []) if isinstance(data, dict) else []:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                continue
            status = row.get("status")
            value = status.get("value") if isinstance(status, dict) else None
            if value in (None, "loaded"):          # None: a plain llama-server (one model, always loaded)
                names.append(row["id"])
        return names

    def slots(self, model: str) -> list[dict]:
        data = json.loads(self._fetch("/slots?model=" + urllib.request.quote(model)).decode("utf-8", "replace"))
        if not isinstance(data, list):
            raise OSError("slots")
        return [{"id": s["id"], "processing": bool(s.get("is_processing")),
                 "task": s.get("id_task") if type(s.get("id_task")) is int else -1}
                for s in data if isinstance(s, dict) and type(s.get("id")) is int]

    def deferred(self, model: str) -> int | None:
        """Requests waiting for a slot (`llamacpp:requests_deferred`), None when /metrics is off."""
        try:
            text = self._fetch("/metrics?model=" + urllib.request.quote(model)).decode("utf-8", "replace")
        except OSError:
            return None
        return parse_metric(text, "llamacpp:requests_deferred")

    def snapshot(self, skip: frozenset = frozenset({"star-embed", "star-embed-ft1", "star-rerank"})) -> tuple[dict, dict]:
        """({model: slots}, {model: queued}) of loaded models; raises OSError when the brain cannot be read.
        Helper models (`skip`: embeddings, reranker) are not asked: they are never a sign of chat."""
        models, queued = {}, {}
        for model in self.loaded_models():
            if model in skip:
                continue
            try:
                models[model] = self.slots(model)
            except (OSError, ValueError):
                continue           # embedding/rerank servers may not offer /slots; they are helpers anyway
            waiting = self.deferred(model)
            if waiting:
                queued[model] = waiting
        return models, queued


def parse_metric(text: str, name: str) -> int | None:
    for line in text.splitlines():
        if line.startswith(name + " ") or line.startswith(name + "{"):
            try:
                return int(float(line.rsplit(None, 1)[-1]))
            except ValueError:
                return None
    return None


# --- Windows PC --------------------------------------------------------------------------------------------------------

def windows_memory() -> tuple[int, int] | None:
    """(total MiB, available MiB) via GlobalMemoryStatusEx, or None."""
    if os.name != "nt":
        return None
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return status.ullTotalPhys // 2**20, status.ullAvailPhys // 2**20


def windows_cpu_times() -> tuple[int, int] | None:
    """(busy, total) 100-ns units via GetSystemTimes (kernel time includes idle), or None."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        return None

    def value(ft):
        return (ft.dwHighDateTime << 32) | ft.dwLowDateTime
    total = value(kernel) + value(user)
    return total - value(idle), total


def parse_nvidia_smi(text: str) -> dict | None:
    """`nvidia-smi --query-gpu=utilization.gpu,memory.total,memory.used --format=csv,noheader,nounits` (first GPU)."""
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            try:
                return {"gpu_util": float(parts[0]) / 100.0, "vram_total_mib": int(float(parts[1])),
                        "vram_used_mib": int(float(parts[2]))}
            except ValueError:
                return None
    return None


def _run(args: list[str], timeout: float = 5.0) -> str | None:
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        done = subprocess.run(args, capture_output=True, timeout=timeout, creationflags=flags)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.decode("utf-8", "replace") if done.returncode == 0 else None


def nvidia_gpu(run=_run) -> dict | None:
    text = run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.total,memory.used", "--format=csv,noheader,nounits"])
    return parse_nvidia_smi(text) if text else None


def nvidia_compute_pids(run=_run) -> set[int] | None:
    text = run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader,nounits"])
    if text is None:
        return None
    return {int(x) for x in text.split() if x.strip().isdigit()}


def windows_process_names(run=_run) -> set[str] | None:
    text = run(["tasklist", "/fo", "csv", "/nh"], timeout=10.0)
    if text is None:
        return None
    names = set()
    for line in text.splitlines():
        if line.startswith('"'):
            names.add(line.split('","', 1)[0].strip('"').lower())
    return names


def fullscreen_foreground() -> str:
    """The foreground window's process name when that window covers its whole monitor (a game or a fullscreen
    video), else "". The desktop and the shell never count."""
    if os.name != "nt":
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd or hwnd in (user32.GetDesktopWindow(), user32.GetShellWindow()):
            return ""
        name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, name, 256)
        if name.value in ("WorkerW", "Progman", "Shell_TrayWnd"):
            return ""
        # Windows' own answer first: 2 = a full-screen app is running, 3 = exclusive Direct3D full screen,
        # 4 = presentation mode. A maximised window (5, "accepts notifications") is not full screen, even when it
        # draws its own title bar (Chrome, Electron apps) and so covers the monitor.
        state = ctypes.c_int(0)
        fullscreen_app = (ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0
                          and state.value in (2, 3, 4))
        if not fullscreen_app:
            if user32.IsZoomed(hwnd):
                return ""
            if user32.GetWindowLongW(hwnd, -16) & 0x00C00000 == 0x00C00000:   # has a title bar
                return ""
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        class MonitorInfo(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                        ("dwFlags", wintypes.DWORD)]
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(MonitorInfo)
        monitor = user32.MonitorFromWindow(hwnd, 2)
        if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return ""
        m = info.rcMonitor
        if not fullscreen_app and not (rect.left <= m.left and rect.top <= m.top and rect.right >= m.right
                                       and rect.bottom >= m.bottom):
            return ""
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)     # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return "a fullscreen window"
        try:
            size = wintypes.DWORD(520)
            path = ctypes.create_unicode_buffer(520)
            if kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
                return os.path.basename(path.value) or "a fullscreen window"
        finally:
            kernel32.CloseHandle(handle)
        return "a fullscreen window"
    except Exception:          # any ctypes surprise: say nothing rather than guess
        return ""


def owner_busy_reason(*, processes: set[str] | None, fullscreen: str, gpu: dict | None,
                      compute_pids: set[int] | None, games=DEFAULT_GAMES, graphics_util: float = 0.6) -> str:
    """Why the owner is using the PC right now, or "". Pure (tests hand in the observations)."""
    wanted = {g.lower() for g in games}
    running = sorted(wanted & (processes or set()))
    if running:
        return f"game running: {running[0]}"
    if fullscreen and fullscreen.lower() not in ("explorer.exe",):
        return f"fullscreen: {fullscreen}"
    # A busy GPU with no compute process at all is graphics work (a game, a render). With STAR's own training on
    # the GPU this signal is blind (its load explains the utilisation); the process list and fullscreen still work.
    if gpu and gpu.get("gpu_util", 0) >= graphics_util and compute_pids is not None and not compute_pids:
        return f"graphics load on the GPU ({gpu['gpu_util']:.0%})"
    return ""


# --- whole-machine snapshots ---------------------------------------------------------------------------------------------

class CpuMeter:
    """Busy share between successive calls (the first call measures over `first_wait` seconds)."""

    def __init__(self, reader=None, first_wait: float = 0.5, sleep=time.sleep):
        self._read = reader or (windows_cpu_times if os.name == "nt" else proc_cpu_times)
        self._last = None
        self._first_wait, self._sleep = first_wait, sleep

    def __call__(self) -> float | None:
        now = self._read()
        if self._last is None and now is not None and self._first_wait > 0:
            self._sleep(self._first_wait)
            self._last, now = now, self._read()
        share = cpu_busy_share(self._last, now)
        self._last = now
        return share


def linux_snapshot(machine: str, *, cpu: CpuMeter, brain: BrainProbe | None = None, lock_dir: str = LOCK_DIR,
                   with_studios: bool = False, clock=time.time) -> dict:
    """A snapshot dict (see agent_resource_planner.MachineSnapshot) of this Linux machine/container."""
    memory = proc_meminfo() or (0, 0)
    total, available = memory
    limit = cgroup_memory_limit_mib()
    if limit and limit < total:          # an LXC container with a memory limit: its own view counts
        total = limit
        available = min(available, limit)
    snap = {"machine": machine, "taken_at": clock(), "cpu_threads": os.cpu_count() or 1,
            "cpu_busy": cpu() or 0.0, "mem_total_mib": total, "mem_available_mib": available,
            "lock_owner": lock_owner(lock_dir)}
    if brain is not None:
        models, queued = brain.snapshot()
        snap["models"], snap["deferred"] = models, queued
    if with_studios:
        snap["studios"] = studio_processes()
    return snap


def pc_snapshot(*, cpu: CpuMeter, run=_run, games=None, clock=time.time) -> dict:
    """A snapshot dict of the owner's Windows PC: RAM, CPU, GPU and whether the owner is busy."""
    memory = windows_memory() or (0, 0)
    gpu = nvidia_gpu(run)
    names = windows_process_names(run)
    configured = os.environ.get("STAR_PLANNER_GAMES")
    game_list = games or (tuple(x.strip() for x in configured.split(",") if x.strip()) if configured else DEFAULT_GAMES)
    reason = owner_busy_reason(processes=names, fullscreen=fullscreen_foreground(), gpu=gpu,
                               compute_pids=nvidia_compute_pids(run) if gpu else None, games=game_list)
    snap = {"machine": "pc", "taken_at": clock(), "cpu_threads": os.cpu_count() or 1, "cpu_busy": cpu() or 0.0,
            "mem_total_mib": memory[0], "mem_available_mib": memory[1], "owner_busy": reason}
    if gpu:
        snap.update(gpu)
    return snap
