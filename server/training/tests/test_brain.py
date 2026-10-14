"""The brain client against a local fake of the llama.cpp router (streaming chat, /slots, /v1/models, embeddings)."""
from __future__ import annotations

import http.server
import json
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest   # noqa: E402

from startrain.brain import Brain, BrainError, Yielded  # noqa: E402


class Router(http.server.BaseHTTPRequestHandler):
    busy = {"star-fast": 1, "star-voice": 0}
    tokens = 40
    delay = 0.1

    def log_message(self, *a):
        pass

    def _send(self, obj, status=200):
        raw = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/v1/models":
            return self._send({"data": [{"id": "star-fast", "aliases": ["star-code"], "status": {"value": "loaded"}},
                                        {"id": "star-voice", "aliases": ["star-quick"], "status": {"value": "loaded"}},
                                        {"id": "star-deep", "status": {"value": "unloaded"}}]})
        if self.path.startswith("/slots?model="):
            model = self.path.split("=", 1)[1]
            return self._send([{"id": i, "is_processing": i < Router.busy.get(model, 0)} for i in range(2)])
        self._send({}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/v1/embeddings":
            return self._send({"data": [{"index": i, "embedding": [1.0, 0.0]} for i, _ in enumerate(body["input"])]})
        if self.path != "/v1/chat/completions":
            return self._send({}, 404)
        if self.headers.get("Authorization") != "Bearer testkey":
            return self._send({"error": "no"}, 401)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for i in range(Router.tokens):
                chunk = {"choices": [{"delta": {"content": f"t{i} "}, "finish_reason": None}]}
                self.wfile.write(b"data: " + json.dumps(chunk).encode() + b"\n\n")
                self.wfile.flush()
                time.sleep(Router.delay)
            done = {"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 7, "completion_tokens": Router.tokens}}
            self.wfile.write(b"data: " + json.dumps(done).encode() + b"\n\ndata: [DONE]\n\n")
        except (BrokenPipeError, ConnectionResetError):
            pass


@pytest.fixture()
def brain(tmp_path):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Router)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    key = tmp_path / "key"
    key.write_text("testkey\n")
    Router.busy = {"star-fast": 1, "star-voice": 0}
    Router.tokens, Router.delay = 40, 0.1
    yield Brain(f"http://127.0.0.1:{server.server_address[1]}", str(key), timeout=30, poll_s=0.3)
    server.shutdown()


def test_streamed_chat_returns_text_and_usage(brain):
    Router.tokens, Router.delay = 5, 0.01
    out = brain.chat("star-fast", [{"role": "user", "content": "hi"}], max_tokens=10)
    assert out["text"] == "t0 t1 t2 t3 t4 " and out["finish"] == "stop" and out["prompt_tokens"] == 7 and out["completion_tokens"] == 5


def test_a_yield_cuts_the_stream_within_a_poll(brain):
    started = time.monotonic()
    with pytest.raises(Yielded) as info:
        brain.chat("star-fast", [{"role": "user", "content": "hi"}], max_tokens=10,
                   should_yield=lambda: "interactive" if time.monotonic() - started > 0.5 else "")
    assert info.value.reason == "interactive"
    assert time.monotonic() - started < 2.0                      # the reply would have taken 4 s
    assert "yield_signalled" in brain.last_trace


def test_other_activity_is_told_apart_from_our_own_request(brain):
    assert brain.others_active(own_model="star-fast") is False          # one busy slot of ours is allowed
    assert brain.others_active(own_model="star-quick") is True          # the alias resolves to star-voice: star-fast is someone else's
    Router.busy["star-fast"] = 2
    assert brain.others_active(own_model="star-code") is True           # a second busy slot on our model
    Router.busy = {"star-fast": 0, "star-voice": 0}
    assert brain.others_active() is False
    assert brain.seconds_since_other_activity() < 60
    Router.busy["star-voice"] = 1
    assert brain.others_active() is True and brain.loaded_models() == ["star-fast", "star-voice"]       # unloaded models are never asked


def test_errors_are_brain_errors(brain, tmp_path):
    bad = Brain(brain._host and f"http://{brain._host}:{brain._port}", str(tmp_path / "missing-key"), poll_s=0.3)
    with pytest.raises(BrainError):
        bad.chat("star-fast", [{"role": "user", "content": "hi"}], max_tokens=5)
    with pytest.raises(BrainError):
        Brain("http://127.0.0.1:9", str(tmp_path / "k"), poll_s=0.3).embed("star-embed", ["x"])
    assert brain.embed("star-embed", ["a", "b"]) == [[1.0, 0.0], [1.0, 0.0]]


def test_the_total_timeout_stops_a_stuck_request(brain, tmp_path):
    slow = Brain(f"http://{brain._host}:{brain._port}", str(tmp_path / "key"), timeout=0.8, poll_s=0.2)
    with pytest.raises(BrainError):
        slow.chat("star-fast", [{"role": "user", "content": "hi"}], max_tokens=10)
