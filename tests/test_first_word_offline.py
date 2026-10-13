"""CI-backed real timers against the full run_task fake stream, no network."""
import warnings

import pytest

from scripts.audit_first_word_offline import PROMPTS, audit, report


def test_real_first_visible_delta_includes_ten_stage_timings(monkeypatch):
    monkeypatch.setenv('STAR_FAST_FIRST_DELTA', '0')
    rows = audit()
    assert len(rows) == len(PROMPTS) == 10
    assert [row.index for row in rows] == list(range(1, 11))
    assert all(row.elapsed_ms > 0 and row.prompt_chars > 0 for row in rows)
    assert all(row.answer.startswith("READY") for row in rows)
    assert all(row.stages_ms["history"] >= 0 for row in rows)
    assert all(row.stages_ms["knowledge"] >= 0 for row in rows)
    assert all(row.stages_ms["documents"] >= 0 for row in rows)
    # Pytest prints the measured table in CI's warning summary; no fabricated numbers.
    warnings.warn("OFFLINE_FIRST_WORD_TABLE\\n" + report(rows), RuntimeWarning, stacklevel=1)


@pytest.mark.parametrize("enabled", [False, True])
def test_first_short_stream_delta_arrives_before_the_second_chunk(monkeypatch, enabled):
    import asyncio
    from types import SimpleNamespace
    from star.agent import read_stream

    monkeypatch.setenv("STAR_FAST_FIRST_DELTA", "1" if enabled else "0")
    received = []

    def chunk(content, finish_reason=None):
        return SimpleNamespace(model="fake", choices=[SimpleNamespace(
            delta=SimpleNamespace(content=content, tool_calls=[]),
            finish_reason=finish_reason)])

    async def sequence():
        yield chunk("Hello")
        # The default behavior remains unchanged; the opted-in run must show
        # a short first delta *before* the second chunk arrives.
        observed = any(event.get("event") == "assistant_delta" and event.get("text") == "Hello"
                       for event in received)
        assert observed is enabled
        yield chunk(" there", "stop")

    result, tools, shown = asyncio.run(read_stream(sequence(), received.append))
    assert result == "Hello there" and tools == [] and shown
    assert "".join(event.get("text", "") for event in received
                   if event.get("event") == "assistant_delta") == result


def test_opt_in_ten_turn_before_after_matches_prompts_answers(monkeypatch):
    monkeypatch.setenv("STAR_FAST_FIRST_DELTA", "0")
    before = audit()
    monkeypatch.setenv("STAR_FAST_FIRST_DELTA", "1")
    after = audit()
    assert [row.prompt_chars for row in before] == [row.prompt_chars for row in after]
    assert [row.answer for row in before] == [row.answer for row in after]
    # This tests only the 90-ms gap in the fake chunk sequence; it does not
    # predict a CPU server's actual inference time.
    assert all(before[i].elapsed_ms - after[i].elapsed_ms > 30 for i in range(1, 10))
    warnings.warn("OFFLINE_FIRST_WORD_BEFORE_AFTER\\nBEFORE\\n" + report(before)
                  + "\\nAFTER\\n" + report(after), RuntimeWarning, stacklevel=1)
