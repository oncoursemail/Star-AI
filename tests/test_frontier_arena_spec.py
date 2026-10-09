from pathlib import Path
import json

HERE = Path(__file__).parents[1]


def test_frontier_arena_spec_is_unique_and_explicit():
    cases=json.loads((HERE / 'evals' / 'frontier_arena_spec.json').read_text(encoding='utf-8'))
    assert len(cases)>=70
    assert len({c['id'] for c in cases}) == len(cases)
    assert all(c['task'] and c['independent_oracle'] and c['hard_failure_condition'] for c in cases)
    assert all(c['fixture_status'] == 'to_implement' for c in cases)
    assert len({c['category'] for c in cases})>=8


def test_frontier_arena_is_specification_not_fake_results():
    cases=json.loads((HERE / 'evals' / 'frontier_arena_spec.json').read_text(encoding='utf-8'))
    forbidden={'passed', 'failed', 'pass_rate', 'run_id', 'latency_ms', 'score'}
    assert all(not forbidden.intersection(c) for c in cases)
