"""A fake brain for the tests and for `dry-run`: a small HTTP server that speaks the parts of the llama.cpp router
night school and the app use (/v1/models, /slots, /v1/chat/completions, streamed or not), with scripted answers.
No model runs and nothing leaves the machine."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import parse_qs, urlsplit

DIAGNOSE_MARK = "night school review"
LESSON = "Keep a number inside a range with math.clamp(value, low, high) instead of chained if statements."


def practice_task(task_id: str, name: str, *, needs: str = "math\\.clamp") -> dict:
    return {
        "id": task_id, "category": "luau", "difficulty": 1, "run_mode": "automated",
        "goal": f"Write {name} as a small typed Luau function",
        "prompt": (f"In my Roblox game: write a Luau function `{name}(value: number): number` that keeps the value "
                   "between 0 and 100. Reply with one fenced Luau block."),
        "required_evidence": ["answer.md"], "pass_conditions": ["All automated checks pass (see auto)"],
        "auto": {"strict": False, "require": [{"id": "uses_expected_call", "re": needs, "why": "the expected call is used"}]},
    }


def dry_tasks() -> list[dict]:
    """Nine tiny tasks. The scripted model solves "easy" ones at once and the others only with the lesson."""
    tasks = [practice_task(f"NSDRY-{i:02d}", name) for i, name in enumerate(
        ["limitHealth", "limitSpeed", "limitStamina", "limitVolume", "limitZoom", "limitHunger"], 1)]
    tasks += [practice_task(f"NSDRY-{i:02d}", name, needs="return") for i, name in enumerate(["easyOne", "easyTwo", "easyThree"], 7)]
    return tasks


def scripted(body: dict) -> str:
    """The fake model: without the lesson in its context it writes chained ifs (fails the check), with it math.clamp."""
    text = json.dumps(body.get("messages", []))
    if DIAGNOSE_MARK in text:
        return json.dumps({"cause": "The answer used chained if statements instead of the clamp call the task expects.",
                           "lesson": LESSON})
    name = next((n for n in ("limitHealth", "limitSpeed", "limitStamina", "limitVolume", "limitZoom", "limitHunger",
                             "easyOne", "easyTwo", "easyThree") if n in text), "limitValue")
    if "math.clamp" in text or name.startswith("easy"):
        code = f"local function {name}(value: number): number\n\treturn math.clamp(value, 0, 100)\nend\n\nreturn {name}"
    else:
        code = (f"local function {name}(value: number): number\n\tif value < 0 then\n\t\treturn 0\n\tend\n"
                f"\tif value > 100 then\n\t\treturn 100\n\tend\n\treturn value\nend\n\nreturn {name}")
    return "Here is the function.\n\n```lua\n" + code + "\n```\n"


class FakeBrain:
    """`with FakeBrain() as brain:` then `brain.url`. `brain.busy[(model, slot)] = True` plays another client."""

    def __init__(self, responder=scripted, models=None):
        self.responder = responder
        self.models = models or {"star-fast": ["star-code", "star-vision"], "star-voice": ["star-quick"]}
        self.busy: dict[tuple[str, int], bool] = {}
        self.tasks: dict[tuple[str, int], int] = {}
        self.requests: list[tuple[str, str, dict]] = []
        self.completions: list[dict] = []
        self.on_completion = None                       # called with the request body before the reply is sent
        brain = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                pass

            def _json(self, status: int, data) -> None:
                raw = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                url = urlsplit(self.path)
                brain.requests.append(("GET", url.path, {}))
                if url.path in ("/v1/models", "/models"):
                    return self._json(200, {"object": "list", "data": [
                        {"id": name, "object": "model", "aliases": aliases, "status": {"value": "loaded"}}
                        for name, aliases in brain.models.items()]})
                if url.path == "/slots":
                    model = (parse_qs(url.query).get("model") or [""])[0]
                    return self._json(200, [{"id": slot, "is_processing": bool(brain.busy.get((model, slot))),
                                             "id_task": brain.tasks.get((model, slot), 0), "n_ctx": 8192}
                                            for slot in (0, 1)])
                if url.path in ("/props", "/v1/props"):
                    return self._json(200, {"default_generation_settings": {"n_ctx": 8192}, "total_slots": 2})
                if url.path == "/health":
                    return self._json(200, {"status": "ok"})
                return self._json(404, {"error": {"message": "not found"}})

            def do_POST(self):
                url = urlsplit(self.path)
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                except ValueError:
                    body = {}
                brain.requests.append(("POST", url.path, body))
                if not url.path.endswith("/chat/completions"):
                    return self._json(404, {"error": {"message": "not found"}})
                brain.completions.append(body)
                model = str(body.get("model") or "")
                real = next((m for m, aliases in brain.models.items() if model == m or model in aliases), model)
                slot = body.get("id_slot") if type(body.get("id_slot")) is int else 0
                brain.tasks[(real, slot)] = brain.tasks.get((real, slot), 0) + 1
                if brain.on_completion:
                    brain.on_completion(body)
                text = brain.responder(body)
                usage = {"prompt_tokens": 50, "completion_tokens": max(1, len(text) // 4), "total_tokens": 60}
                if not body.get("stream"):
                    return self._json(200, {"id": "fake", "object": "chat.completion", "created": 0, "model": model,
                                            "choices": [{"index": 0, "finish_reason": "stop",
                                                         "message": {"role": "assistant", "content": text}}],
                                            "usage": usage})
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Connection", "close")
                self.end_headers()
                base = {"id": "fake", "object": "chat.completion.chunk", "created": 0, "model": model}
                events = [{**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]}]
                events += [{**base, "choices": [{"index": 0, "delta": {"content": text[i:i + 40]}, "finish_reason": None}]}
                           for i in range(0, len(text), 40)]
                events.append({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
                events.append({**base, "choices": [], "usage": usage})
                for event in events:
                    self.wfile.write(b"data: " + json.dumps(event).encode("utf-8") + b"\n\n")
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                self.close_connection = True

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.handle_error = lambda *_args: None      # a client that hangs up (a cancelled request) is normal
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._server.shutdown()
        self._server.server_close()


def luau_ok(code: str, strict: bool = False) -> dict:
    """Stand-in for the knowledge service's static check (used when that service is not asked)."""
    return {"ran": True, "ok": True, "compiled": True, "analyzed": True, "errors": [], "error_count": 0,
            "warnings": [], "notes": [], "roblox_api_types": True, "executed": False}
