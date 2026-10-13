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
