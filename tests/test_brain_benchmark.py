"""Tests do not claim any real model benchmark was run."""
import pytest
from star.brain_benchmark import local_endpoint, parse_sse_data, summarize


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
