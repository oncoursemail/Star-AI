"""Take Studio back to Edit mode when a playtest stop did not stick.

Live 2026-10-16 (Studio machine): the connector's stop answered "Game Stopped" and Studio stayed in Play; only a click
on Studio's own Stop button on the server display helped, and until then the daily playtest run and the Studio Lab
nightly found no Edit place. PlayGuard.ensure_edit() checks the connector's state call, waits a little, then presses
Stop on the display (xdotool, Shift+F5) and checks again. If Studio is still in Play it says so (edit=False) and the
caller skips the run instead of hanging. Unknown state (no answer, odd text) never sends a key press.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time

STOP_KEY = "shift+F5"                       # Studio's Stop shortcut
WINDOW_PATTERN = " - Roblox Studio$"        # main window title: "<place> - Roblox Studio"
WAIT_SECONDS = 8.0


def display_stop(*, run=subprocess.run, which=shutil.which, pause=time.sleep, display: str | None = None) -> dict:
    """Press Studio's Stop (Shift+F5) on the server display. Blocking; runs on the machine that owns the display."""
    tool = which("xdotool")
    if not tool:
        return {"ok": False, "detail": "xdotool is not installed"}
    env = {**os.environ, "DISPLAY": display or os.environ.get("STAR_STUDIO_DISPLAY") or ":1"}
    try:
        found = run([tool, "search", "--onlyvisible", "--name", WINDOW_PATTERN], capture_output=True, text=True,
                    timeout=15, env=env)
        windows = found.stdout.split()
        if not windows:
            return {"ok": False, "detail": "no Studio window on the display"}
        run([tool, "windowactivate", windows[0]], capture_output=True, text=True, timeout=15, env=env)
        pause(0.5)
        done = run([tool, "key", "--clearmodifiers", STOP_KEY], capture_output=True, text=True, timeout=15, env=env)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "detail": type(error).__name__}
    return {"ok": done.returncode == 0, "window": windows[0], "key": STOP_KEY,
            "detail": "" if done.returncode == 0 else (done.stderr or "")[:200]}


class PlayGuard:
    """get_state: async callable -> "Edit", "Playing" or None (unknown). request_stop: async connector stop (optional)."""

    def __init__(self, get_state, *, request_stop=None, press_stop=None, sleep=asyncio.sleep,
                 clock=time.monotonic, wait: float | None = None, poll: float = 1.0, log=print):
        self.get_state, self.request_stop = get_state, request_stop
        self.press_stop = display_stop if press_stop is None else press_stop
        self.sleep, self.clock, self.poll, self.log = sleep, clock, poll, log
        self.wait = WAIT_SECONDS if wait is None else wait

    async def _state(self) -> str | None:
        try:
            return await self.get_state()
        except Exception:
            return None

    async def _wait_edit(self) -> bool:
        end = self.clock() + self.wait
        while True:
            if await self._state() == "Edit":
                return True
            if self.clock() >= end:
                return False
            await self.sleep(self.poll)

    async def ensure_edit(self, *, send_stop: bool = False) -> dict:
        """edit True: Studio is in Edit; False: still in Play after the display fallback; None: state unknown.
        send_stop: also send the connector stop first (use when no stop was sent yet)."""
        began = self.clock()
        mode = await self._state()
        if mode == "Edit":
            return {"edit": True, "method": "edit", "seconds": 0.0}
        if mode != "Playing":
            return {"edit": None, "method": "unknown", "seconds": 0.0}
        result: dict = {"edit": False, "method": "stuck"}
        if send_stop and self.request_stop is not None:
            try:
                await self.request_stop()
            except Exception as error:
                result["stop_error"] = type(error).__name__
        if await self._wait_edit():
            result.update(edit=True, method="connector")
        else:
            self.log(f"Studio is still in Play {self.wait:.0f}s after the stop: pressing Stop on the display")
            if self.press_stop is not None:
                pressed = await asyncio.to_thread(self.press_stop)
                result["display"] = pressed
                if await self._wait_edit():
                    result.update(edit=True, method="display")
        result["seconds"] = round(self.clock() - began, 1)
        if result["edit"]:
            self.log(f"Studio back in Edit mode via {result['method']} after {result['seconds']}s")
        else:
            self.log("STUCK IN PLAY: Studio did not leave Play mode (connector stop and display Stop both tried); "
                     "skipping the run")
        return result


def play_guard(session, studio_id: str, **kwargs) -> PlayGuard:
    """A PlayGuard on a raw connector session for one Studio instance."""
    from .studio_loop import _play_state

    async def state():
        return _play_state(await session.call_tool("get_studio_state", arguments={"studio_id": studio_id}))

    async def stop():
        await session.call_tool("start_stop_play", arguments={"studio_id": studio_id, "is_start": False})
    return PlayGuard(state, request_stop=stop, **kwargs)
