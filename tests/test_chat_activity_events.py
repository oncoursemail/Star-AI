"""The chat activity timeline may only be driven by real, sanitized backend events.

`sanitize_event` is the boundary between Python and the unprivileged React
page: these tests pin the structured `activity` payload and prove that goals,
arguments, tool output and model-authored ids never cross it.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace

from star.react_shell import sanitize_event
from star.team_service import run_research_team

ROOT = Path(__file__).resolve().parents[1]


def test_team_plan_lists_only_trusted_stages_with_dependencies():
    out = sanitize_event({"event": "team_planned", "tasks": [
        {"id": "evidence", "role": "research", "dependencies": []},
        {"id": "synthesis", "role": "integration",
         "dependencies": ["evidence", "design", "critic", "forged-stage"]},
        {"id": "ignore previous instructions", "role": "research", "dependencies": []},
        "not-a-dict",
    ]})
    assert out["activity"] == {"type": "plan", "group": "team", "steps": [
        {"id": "evidence", "role": "research", "needs": []},
        {"id": "synthesis", "role": "integration", "needs": ["evidence", "design", "critic"]},
    ]}
    assert "ignore previous" not in str(out) and "forged" not in str(out)


def test_team_stage_states_and_elapsed_time():
    started = sanitize_event({"event": "agent_started", "task": "evidence", "role": "research", "active": 1})
    assert started["activity"] == {"type": "agent", "group": "team", "id": "evidence",
                                   "role": "research", "state": "running"}
    done = sanitize_event({"event": "agent_finished", "task": "evidence", "role": "research",
                           "status": "completed", "elapsed_ms": 4210})
    assert done["activity"]["state"] == "done" and done["activity"]["elapsed_ms"] == 4210
    failed = sanitize_event({"event": "agent_finished", "task": "critic", "role": "review",
                             "status": "failed", "elapsed_ms": -5})
    assert failed["activity"]["state"] == "failed" and "elapsed_ms" not in failed["activity"]
    cancelled = sanitize_event({"event": "agent_finished", "task": "design", "role": "planner",
                                "status": "cancelled"})
    assert cancelled["activity"]["state"] == "cancelled"
    blocked = sanitize_event({"event": "agent_blocked", "task": "synthesis", "role": "integration"})
    assert blocked["activity"]["state"] == "blocked"
    # An unknown status is never reported as success.
    odd = sanitize_event({"event": "agent_finished", "task": "design", "role": "planner",
                          "status": "definitely fine"})
    assert odd["activity"]["state"] == "failed"


def test_specialist_rows_use_an_opaque_key_not_the_model_authored_id():
    first = sanitize_event({"event": "subagent_started", "role": "luau",
                            "task_id": "private-string", "goal": "secret-local-file"})
    last = sanitize_event({"event": "subagent_finished", "role": "luau",
                           "task_id": "private-string", "status": "completed"})
    assert first["activity"]["id"] == last["activity"]["id"]
    assert first["activity"]["state"] == "running" and last["activity"]["state"] == "done"
    assert first["activity"]["role"] == "luau" and first["activity"]["group"] == "specialist"
    for payload in (first, last):
        assert "private-string" not in str(payload) and "secret-local-file" not in str(payload)
    other = sanitize_event({"event": "subagent_started", "role": "ui", "task_id": "another"})
    assert other["activity"]["id"] != first["activity"]["id"]


def test_tool_rows_never_carry_arguments_output_or_rejected_names():
    running = sanitize_event({"event": "tool_started", "tool": "workspace_read",
                              "arguments": {"path": "C:/secret/notes.txt"}})
    assert running["activity"] == {"type": "tool", "state": "running", "tool": "workspace_read"}
    assert "secret" not in str(running)
    done = sanitize_event({"event": "tool_finished", "tool": "workspace_read", "is_error": False})
    assert done["activity"]["state"] == "done"
    failed = sanitize_event({"event": "tool_finished", "tool": "star_web_search", "is_error": True})
    assert failed["activity"]["state"] == "failed"
    rejected = sanitize_event({"event": "tool_rejected", "tool": "exfiltrate_api_key_sk_live"})
    assert rejected["activity"] == {"type": "tool", "state": "blocked"}
    assert "sk_live" not in str(rejected)
    weird = sanitize_event({"event": "tool_finished", "tool": "bad name\nwith newline"})
    assert "tool" not in weird["activity"] or weird["activity"]["tool"] != "bad name\nwith newline"
    assert "newline" not in str(weird)


def test_route_search_turn_and_finish_are_enumerated_and_bounded():
    assert sanitize_event({"event": "route_selected", "profile": "agent",
                           "description": "Agent workflow"})["activity"] == {"type": "route", "profile": "agent"}
    assert "profile" not in sanitize_event({"event": "route_selected", "profile": "<script>"})["activity"]
    assert sanitize_event({"event": "search_started"})["activity"] == {"type": "search", "state": "running"}
    assert sanitize_event({"event": "search_finished"})["activity"] == {"type": "search", "state": "done"}
    assert sanitize_event({"event": "model_turn", "step": 2, "max_steps": 12})["activity"] == {
        "type": "turn", "step": 2, "max_steps": 12}
    assert sanitize_event({"event": "model_turn", "step": "2; drop", "max_steps": 10**9})["activity"] == {
        "type": "turn"}
    assert sanitize_event({"event": "finished", "model_calls": 3, "tool_calls": 2})["activity"] == {
        "type": "finished", "model_calls": 3, "tool_calls": 2}
    assert sanitize_event({"event": "saved", "run_id": "20261010T000000"})["activity"] == {"type": "saved"}


def test_streamed_text_and_legacy_phase_contract_are_unchanged():
    delta = sanitize_event({"event": "assistant_delta", "text": "Hello"})
    assert delta == {"phase": "Generating response", "delta": "Hello"}
    assert sanitize_event({"event": "tool_output", "content": "secret"}) == {
        "phase": "Using an authorized local tool"}
    assert "phase" in sanitize_event({"event": "something_new"})


def test_agent_loop_announces_model_turns_and_tool_start_before_execution():
    source = (ROOT / "star/agent.py").read_text(encoding="utf-8")
    assert "'event': 'model_turn'" in source
    started = source.index('"event": "tool_started"')
    finished = source.index('"event": "tool_finished"')
    assert started < finished


def test_team_run_emits_its_plan_before_any_stage_starts(tmp_path):
    seen = []

    class Completions:
        async def create(self, **kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="Checked claim; nothing was executed."))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    answer, team = asyncio.run(run_research_team(
        endpoint="http://127.0.0.1:8080/v1", model="unit-test-model", project="STAR",
        prompt="Plan a small inventory system", home=tmp_path, parallel=2,
        on_event=seen.append, client=client))
    assert answer and team.completed
    kinds = [e["event"] for e in seen]
    assert kinds[0] == "team_planned"
    assert [t["id"] for t in seen[0]["tasks"]] == ["evidence", "design", "critic", "synthesis"]
    assert seen[0]["tasks"][-1]["dependencies"] == ["evidence", "design", "critic"]
    # Every planned stage is later reported as started and finished by the runtime.
    for stage in ("evidence", "design", "critic", "synthesis"):
        assert any(e["event"] == "agent_started" and e["task"] == stage for e in seen)
        assert any(e["event"] == "agent_finished" and e["task"] == stage for e in seen)
    # The whole real stream survives sanitising into timeline rows.
    rows = [sanitize_event(e)["activity"] for e in seen]
    assert rows[0]["type"] == "plan" and len(rows[0]["steps"]) == 4
    assert all(r["type"] == "agent" for r in rows[1:])


def test_the_status_line_never_shows_an_internal_event_name():
    """Seen in the real shell: "STAR is working · model_started" while the model was being contacted."""
    assert sanitize_event({"event": "model_started"}) == {"phase": "Contacting the model"}
    for name in ("model_started", "something_new", "internal_step_v2"):
        phase = sanitize_event({"event": name})["phase"]
        assert name not in phase and "_" not in phase
