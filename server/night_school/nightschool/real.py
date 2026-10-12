"""The real answer path: the application's own `star.desktop_core.run_task` (the function the app and the
evaluation runner call), the app's own scorer `star.eval_checks.score_answer`, and the app's own lesson store.

What is the same as in the installed app: routing, system prompt, skill packs, documentation search, the Luau
self-check and repair, and the way lessons enter a turn (`LessonStore.recall` under the app's lessons heading).
What differs, on purpose: the app data folder is a new empty one for every answer (nothing of the owner's profile
exists on the server), night school's lessons are approved inside that throw-away folder by code (in the app only
the owner can approve a lesson), and every model request is pinned to night school's own slot (never slot 0).
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time

from .engine import Result, Yielded, scrub
from .fake import DIAGNOSE_MARK
from .idle import read_key

PROJECT = "night-school"
DIAGNOSE_SYSTEM = (
    "This is a " + DIAGNOSE_MARK + ". You are given a Roblox Luau task, an answer that failed automatic checks, and "
    "the failed checks. Reply with JSON only, no other text: {\"cause\": \"one sentence: why the answer failed\", "
    "\"lesson\": \"ONE short general rule, at most 200 characters, that would prevent this kind of mistake in other "
    "tasks\"}. The lesson must be general: no code block, no names taken from this task.")


class SlotRefused(RuntimeError):
    pass


def bootstrap(settings) -> str:
    """Make the application importable and hand it the server key through this process' environment only.
    The key is read from its file, kept in memory and never printed or logged."""
    app = str(settings.app)
    if app not in sys.path:
        sys.path.insert(0, app)
    key = read_key(settings.key_file)
    if key:
        os.environ["STAR_SERVER_API_KEY"] = key
    if settings.packs:
        os.environ["STAR_SKILL_PACKS"] = settings.packs
    return key


def pin_slots(slot_of):
    """Every chat request the application sends carries `id_slot = slot_of(model)`. Done at the HTTP layer, so it
    also covers the helper calls (summaries, repairs, sub-agents) that the application sends without a slot number.
    Returns a function that puts the application's own client factory back."""
    import httpx
    from star import providers

    class PinTransport(httpx.AsyncBaseTransport):
        def __init__(self):
            self._inner = httpx.AsyncHTTPTransport(trust_env=False)

        async def handle_async_request(self, request):
            if request.method == "POST" and request.url.path.endswith("/completions"):
                body = json.loads((await request.aread()).decode("utf-8"))
                body["id_slot"] = slot_of(str(body.get("model") or ""))
                headers = [(k, v) for k, v in request.headers.raw if k.lower() != b"content-length"]
                request = httpx.Request(request.method, request.url, headers=headers,
                                        content=json.dumps(body).encode("utf-8"), extensions=request.extensions)
            return await self._inner.handle_async_request(request)

        async def aclose(self):
            await self._inner.aclose()


    def open_client(settings, *, request_timeout: float | None = None):
        from openai import AsyncOpenAI
        endpoint, key = providers.connection_for(settings)
        limits = providers.call_limits(settings)
        timeout = httpx.Timeout(request_timeout or limits.request_timeout, connect=limits.connect_timeout)
        client = httpx.AsyncClient(trust_env=False, timeout=timeout, transport=PinTransport())
        return AsyncOpenAI(base_url=endpoint, api_key=key, timeout=timeout, max_retries=0, http_client=client)

    replaced = []
    for module in list(sys.modules.values()):
        name = getattr(module, "__name__", "")
        if (name == "star" or name.startswith("star.")) and getattr(module, "open_client", None) is not None:
            replaced.append((module, module.open_client))
            module.open_client = open_client

    def undo() -> None:
        for module, original in replaced:
            module.open_client = original
    return undo


class LocalSandbox:
    """The evaluation sandbox's own script (prlimit, timeout, empty folder), run here instead of over SSH: night
    school already runs inside the server container as the unprivileged service user."""

    def __init__(self, luau: str, *, mem_mb: int = 256, cpu_s: int = 8, wall_s: int = 15):
        self.luau, self.limits = luau, {"mem_mb": mem_mb, "cpu_s": cpu_s, "wall_s": wall_s}

    def run(self, source: str):
        from star.eval_sandbox import SandboxResult, build_remote_script, parse_status
        started = time.monotonic()
        try:
            done = subprocess.run(["bash", "-s"], input=build_remote_script(source, luau=self.luau, **self.limits).encode("utf-8"),
                                  capture_output=True, timeout=self.limits["wall_s"] + 40)
        except subprocess.TimeoutExpired:
            return SandboxResult(error="the sandbox timed out", seconds=time.monotonic() - started)
        except OSError as exc:
            return SandboxResult(error="could not start the sandbox (" + type(exc).__name__ + ")")
        text = done.stdout.decode("utf-8", "replace")
        if done.returncode != 0 and "@@RC" not in text:
            return SandboxResult(error=f"sandbox failed (status {done.returncode})", seconds=time.monotonic() - started)
        rc, output = parse_status(text)
        if rc == 127 or (rc != 0 and "@@" not in output and "No such file" in output):
            return SandboxResult(error="the Luau VM is not installed where expected")
        return SandboxResult(rc=rc, stdout=output, timed_out=rc in (124, 137, 9) and "@@DONE" not in output,
                             seconds=round(time.monotonic() - started, 2))


def seed_lessons(home: Path, project: str, lessons: list[dict], prompt: str) -> list[str]:
    """Put night school's lessons into the app's lesson store of a throw-away data folder, trusted, and return the
    ids of those the app's own recall would place in this turn."""
    if not lessons:
        return []
    from star import lessons as learning
    store = learning.LessonStore(home)
    try:
        for lesson in lessons:
            captured = store.capture_inferred(project=project, kind="correction", text=lesson["text"],
                                              source_type="verified-fix", source="night-school:" + lesson["id"])
            if captured.lesson_id is not None and captured.status != "refused":
                store.approve(project, captured.lesson_id, human_approved=True, keep_both=True)
        limit, budget = learning.RECALL_FULL
        recalled = store.recall(project, prompt, limit=limit, max_chars=budget)
        return [l.source.split(":", 1)[1] for l in recalled if l.source.startswith("night-school:")]
    finally:
        store.close()


class RealModel:
    """`solve` and `diagnose` for the engine. `gate` is the IdleGate; it is asked before every request and watched
    during it. `luau_check` and `sandbox` can be handed in (tests, dry run)."""

    def __init__(self, settings, gate, *, server: str = "", knowledge: str = "", luau_check=None, sandbox=None,
                 stop=lambda: False, wait: bool = True):
        from star.desktop_core import Settings as AppSettings
        from star.doc_knowledge import client_for
        self.settings, self.gate, self.stop, self._wait = settings, gate, stop, wait
        self.prelude = ""
        self._slots: dict[str, int] = {}
        self._slots_at = -1e9
        self._refusal = ""
        self.app_settings = AppSettings(provider="star_server", server_endpoint=(server or settings.brain_url).rstrip("/") + "/v1",
                                        model=settings.model, project=PROJECT, server_timeout=1800,
                                        knowledge_endpoint=knowledge)
        self.app_settings.validate()
        self._knowledge = client_for(self.app_settings)
        self._luau_check = luau_check
        self._sandbox = sandbox or LocalSandbox(settings.luau_vm)
        self.close = pin_slots(self.slot_of)      # close() gives the application its own client factory back

    # --- slot and politeness ----------------------------------------------------------------------------
    def slot_of(self, model: str) -> int:
        if time.monotonic() - self._slots_at > 600:
            try:
                self._slots = self.gate.watch.slot_for(self.settings.slot)
                self._slots_at = time.monotonic()
            except OSError:
                pass
        slot = self._slots.get(model, self.settings.slot)
        if slot <= 0:
            self._refusal = "night school never uses slot 0 (this model has a single slot: " + model[:40] + ")"
            raise SlotRefused(self._refusal)
        return slot

    def _ready(self) -> None:
        if self._wait and not self.gate.wait(self.stop):
            raise Yielded("stopping")
        if self.stop():
            raise Yielded("stopping")

    def _watched(self, work):
        """Run `work(cancel)` while a watcher looks for another client every `watch_s` seconds."""
        cancel, done, why = threading.Event(), threading.Event(), {"text": ""}

        def watch():
            while not done.wait(self.settings.watch_s):
                reason = "stopping" if self.stop() else self.gate.intruder(self.settings.slot)
                if reason:
                    why["text"] = reason
                    cancel.set()
                    return
        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        try:
            return work(cancel)
        except Yielded:
            raise
        except Exception:
            if cancel.is_set():
                raise Yielded(why["text"]) from None
            raise
        finally:
            done.set()
            watcher.join(self.settings.watch_s + 8)
            self.gate.own_work_done()
            if cancel.is_set():
                raise Yielded(why["text"])

    def check_lesson(self, text: str) -> str:
        """The app's own rule for a lesson text (no secret, no grant of permissions); "" when refused."""
        from star.lessons import LessonRefused, check_lesson_text
        try:
            return check_lesson_text(text)
        except (LessonRefused, ValueError):
            return ""

    # --- scoring -------------------------------------------------------------------------------------------
    def luau_check(self, code: str, strict: bool = False):
        if self._luau_check is not None:
            return self._luau_check(code, strict=strict)
        if self._knowledge is None:
            raise OSError("the knowledge service is not configured")
        last = None
        for attempt in range(3):
            try:
                return self._knowledge.luau_check(code, strict=strict)
            except OSError as exc:
                last = exc
                time.sleep(2 * (attempt + 1))
        raise last

    def score(self, task: dict, answer: str):
        from star import eval_checks as checks
        return checks.score_answer(task, answer, luau_check=self.luau_check, sandbox=self._sandbox,
                                   prelude=self.prelude, test_body=task.get("_test_body", ""))

    # --- the two calls the engine needs --------------------------------------------------------------------
    def solve(self, task: dict, lessons: list[dict]) -> Result:
        from star import eval_checks as checks
        from star.desktop_core import Settings as AppSettings, app_data, run_task
        from star.eval_runner import PRODUCT_FAILURES, isolated_appdata
        self._ready()
        self._refusal = ""
        started = time.monotonic()
        recalled: list[str] = []
        project = "ns-" + re.sub(r"[^a-z0-9-]", "-", task["id"].lower())[:60]
        turn = AppSettings(**{**self.app_settings.__dict__, "project": project})

        def work(cancel):
            with isolated_appdata():
                home = app_data()
                home.mkdir(parents=True, exist_ok=True)
                recalled.extend(seed_lessons(home, project, lessons, task["prompt"]))
                return run_task(turn, task["prompt"], mode=self.settings.mode, cancel_event=cancel)
        try:
            answer = self._watched(work)
        except Yielded:
            raise
        except Exception as exc:
            text = self._refusal or scrub(f"{type(exc).__name__}: {exc}")[:200]
            seconds = time.monotonic() - started
            if any(mark in str(exc) for mark in PRODUCT_FAILURES):
                return Result(False, ["STAR gave no answer: " + text], [], "", seconds, recalled)
            return Result(error=text, seconds=seconds, recalled=recalled)
        seconds = time.monotonic() - started
        if self._refusal:
            return Result(error=self._refusal, seconds=seconds, recalled=recalled)
        try:
            score = self.score(task, answer)
        except checks.InfraError as exc:
            return Result(error=scrub(str(exc))[:200], answer=answer, seconds=seconds, recalled=recalled)
        return Result(score.passed, [scrub(r) for r in score.reasons], [c.record() for c in score.checks],
                      answer, seconds, recalled)

    def diagnose(self, task: dict, result: Result) -> dict:
        from star import providers
        self._ready()
        messages = [
            {"role": "system", "content": DIAGNOSE_SYSTEM},
            {"role": "user", "content": "TASK:\n" + task["prompt"][:1500] + "\n\nFAILED CHECKS:\n"
             + "\n".join(str(r)[:300] for r in result.reasons[:5]) + "\n\nANSWER (may be cut):\n" + result.answer[:2500]}]

        async def ask(cancel):
            async with providers.open_client(self.app_settings) as client:
                job = asyncio.ensure_future(client.chat.completions.create(
                    model=self.settings.model, messages=messages, max_tokens=260, temperature=0.2,
                    extra_body={"cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}))
                while not job.done():
                    if cancel.is_set():
                        job.cancel()
                        raise Yielded("another client")
                    await asyncio.wait({job}, timeout=1.0)
                return job.result().choices[0].message.content or ""
        try:
            reply = self._watched(lambda cancel: asyncio.run(ask(cancel)))
        except Yielded:
            raise
        except Exception:
            return {}
        return parse_diagnosis(reply)


def parse_diagnosis(reply: str) -> dict:
    """{cause, lesson} from the model's reply; {} when it is not usable."""
    found = re.search(r"\{.*\}", reply or "", re.S)
    if found:
        try:
            data = json.loads(found.group(0))
            if isinstance(data, dict):
                return {"cause": str(data.get("cause") or "")[:300], "lesson": str(data.get("lesson") or "")[:400]}
        except ValueError:
            pass
    cause = re.search(r"cause\W{1,4}(.+)", reply or "", re.I)
    lesson = re.search(r"lesson\W{1,4}(.+)", reply or "", re.I)
    return {"cause": cause.group(1).strip()[:300] if cause else "", "lesson": lesson.group(1).strip()[:400] if lesson else ""}


def export_outbox(settings, state: dict) -> dict:
    """Write what night school learned in the repository's own formats, for a pull request. The installed app has
    no way to read lessons from the server, so this folder is the only way out today."""
    from star.lessons import LessonStore, write_export
    outbox = Path(settings.outbox)
    outbox.mkdir(parents=True, exist_ok=True)
    active = sorted((l for l in state.get("lessons", {}).values() if l["status"] == "active"), key=lambda l: l["id"])
    with tempfile.TemporaryDirectory(prefix="ns-outbox-") as folder:
        store = LessonStore(Path(folder))
        try:
            for lesson in active:
                proof = lesson.get("promotion", {})
                store.capture_inferred(
                    project=PROJECT, kind="correction", text=lesson["text"], source_type="verified-fix",
                    source="night-school:" + lesson["id"],
                    evidence=scrub(f"night school: fixed practice tasks {', '.join(proof.get('fixed_tasks', []))}; validation "
                                   f"slice {proof.get('validation_before', '?')} -> {proof.get('validation_with', '?')}"))
            data = store.export(PROJECT)
        finally:
            store.close()
    data["note"] = ("Written by STAR night school on the server. Every lesson is a CANDIDATE: it fixed at least two "
                    "practice tasks and did not lower the validation slice, but no person has reviewed it.")
    write_export(outbox / "star-lessons-night-school.json", data)
    newest: dict[str, dict] = {}
    examples = Path(settings.data) / "examples.jsonl"
    if examples.is_file():
        for line in examples.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            newest[row["task"]] = row
    with open(outbox / "worked-examples.jsonl", "w", encoding="utf-8", newline="\n") as handle:
        for task_id, row in sorted(newest.items()):
            handle.write(json.dumps({
                "id": "night-school-" + task_id, "group_id": task_id, "task_category": row.get("category", ""),
                "instruction": row["prompt"], "response": scrub(row["answer"]),
                "evidence": ["night-school automated checks: " + ", ".join(str(c) for c in row.get("checks", []))[:150]],
                "source": "night-school-verified", "reviewed": False, "rights_confirmed": False,
                "lessons_in_context": row.get("lessons", [])}, ensure_ascii=False) + "\n")
    (outbox / "README.txt").write_text(
        "STAR night school outbox\n\n"
        "star-lessons-night-school.json  promoted lessons in the app's export format (star-lessons-v1), as candidates\n"
        "worked-examples.jsonl           the newest verified answer per practice task (instruction / response rows;\n"
        "                                reviewed=false: a person must review them before any training use)\n\n"
        "The installed app cannot read this folder. These files reach STAR only through a pull request and the\n"
        "next release.\n", encoding="utf-8")
    return {"lessons": len(active), "examples": len(newest)}
