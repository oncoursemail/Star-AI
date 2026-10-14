"""Tests do not claim any real model benchmark was run."""
import pytest
from contextlib import contextmanager
from threading import Barrier, Lock
from star.brain_benchmark import local_endpoint, parse_sse_data, summarize, run_samples


def test_benchmark_allows_only_loopback_api():
    assert local_endpoint("http://127.0.0.1:8080/v1") == "http://127.0.0.1:8080/v1"
    assert local_endpoint("http://localhost:1234/v1/") == "http://localhost:1234/v1"
    for bad in ("https://api.example.com/v1", "http://127.0.0.1:8080/admin",
                "http://127.0.0.1:8080/v1?token=x", "http://localhost:80/v1",
                "http://localhost:8080/v1#frag", "http://user:pw@127.0.0.1:8080/v1",
                "http://0.0.0.0:8080/v1", "file:///etc/passwd"):
        with pytest.raises(ValueError):
            local_endpoint(bad)


def test_sse_parser_discards_incomplete_or_nondata_frames():
    assert parse_sse_data("data: [DONE]") is None
    assert parse_sse_data("not data") is None
    assert parse_sse_data("data: {broken}") is None
    assert parse_sse_data('data: {"choices": [{"delta": {"content": "hi"}}]}')["choices"][0]["delta"]["content"] == "hi"


def test_aggregator_reports_measured_not_invented_numbers():
    samples = [
        {"ttft_ms": 100, "total_ms": 800, "output_chars_per_s": 50},
        {"ttft_ms": 80, "total_ms": 1000, "output_chars_per_s": 40},
        {"ttft_ms": 90, "total_ms": 850, "output_chars_per_s": 60},
    ]
    summary = summarize(samples)
    assert summary["runs"] == 3
    assert summary["median_ttft_ms"] == 90
    assert summary["p95_total_ms"] == 1000
    assert summary["median_output_chars_per_s"] == 50
    with pytest.raises(ValueError):
        summarize([])


def test_concurrent_model_benchmark_measures_real_parallel_requests_and_cache_counters():
    # A fake HTTP stream exercises concurrent scheduling without starting a model.
    barrier = Barrier(2, timeout=2)
    lock = Lock()

    class FakeResponse:
        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
            yield ('data: {"choices":[],"timings":'
                   '{"prompt_n":35,"cache_n":100,"prompt_ms":800.5,"predicted_n":2}}')
            yield 'data: [DONE]'

    class FakeClient:
        def __init__(self):
            self.active = 0
            self.peak = 0
            self.calls = []

        @contextmanager
        def stream(self, method, url, *, json, headers):
            assert method == "POST" and url == "http://127.0.0.1:8080/v1/chat/completions"
            assert json["stream"] is True and json["max_tokens"] == 32
            with lock:
                self.active += 1
                self.peak = max(self.active, self.peak)
                self.calls.append(json["model"])
            try:
                barrier.wait()
                yield FakeResponse()
            finally:
                with lock:
                    self.active -= 1

    client = FakeClient()
    measurements, wall_ms = run_samples(client, "http://127.0.0.1:8080/v1", "local-model",
                                         "Test prompt", runs=2, parallel=2, max_tokens=32)
    assert client.peak == 2
    assert client.active == 0
    assert client.calls == ["local-model", "local-model"]
    assert all(row["actual_completion_tokens"] == 2 for row in measurements)
    assert all(row["prompt_tokens_cached"] == 100 for row in measurements)
    assert all(row["prompt_tokens_evaluated"] == 35 for row in measurements)
    summary = summarize(measurements, wall_ms=wall_ms, parallel=2)
    assert summary["median_prompt_tokens_cached"] == 100
    assert summary["median_prompt_tokens_evaluated"] == 35
    assert summary["median_prompt_eval_ms"] == 800.5
    assert summary["aggregate_output_tokens_per_second"] > 0
    assert summary["parallel"] == 2 and summary["requests_per_second"] > 0
    assert "queueing" in summary["note"]


def test_concurrent_benchmark_rejects_unbounded_work_without_network():
    for runs, parallel in ((0, 1), (11, 1), (2, 0), (2, 3), (10, 5), (2, True)):
        with pytest.raises(ValueError):
            run_samples(object(), "http://127.0.0.1:8080/v1", "local-model",
                        "Test", runs=runs, parallel=parallel)
    with pytest.raises(ValueError):
        summarize([{"ttft_ms": 1}], wall_ms=0)
    with pytest.raises(ValueError):
        summarize([{"ttft_ms": 1}], parallel=5)


def test_cache_metrics_are_not_invented_without_server_timings():
    rows = [{"ttft_ms": 90, "total_ms": 150, "output_chars_per_s": 20,
             "actual_completion_tokens": None}]
    result = summarize(rows, wall_ms=150)
    assert "median_prompt_tokens_cached" not in result
    assert "median_prompt_eval_ms" not in result
    assert "aggregate_output_tokens_per_second" not in result
