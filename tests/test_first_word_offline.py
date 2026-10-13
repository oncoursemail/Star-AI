"""CI-backed real timers against the full run_task fake stream, no network."""
import warnings

from scripts.audit_first_word_offline import PROMPTS, audit, report


def test_real_first_visible_delta_includes_ten_stage_timings():
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


def test_first_short_stream_delta_arrives_before_the_second_chunk():
    import asyncio
    from types import SimpleNamespace
    from star.agent import read_stream

    received = []

    def chunk(content, finish_reason=None):
        return SimpleNamespace(model="fake", choices=[SimpleNamespace(
            delta=SimpleNamespace(content=content, tool_calls=[]),
            finish_reason=finish_reason)])

    async def sequence():
        yield chunk("Hello")
        # Runs as the stream consumer requests the next chunk; the first delta
        # must already be in received, without waiting for chunk two.
        assert any(event.get("event") == "assistant_delta" and event.get("text") == "Hello"
                   for event in received)
        yield chunk(" there", "stop")

    result, tools, shown = asyncio.run(read_stream(sequence(), received.append))
    assert result == "Hello there" and tools == [] and shown
    assert "".join(event.get("text", "") for event in received
                   if event.get("event") == "assistant_delta") == result
