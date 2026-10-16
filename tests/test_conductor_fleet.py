"""Transport-faked acceptance checks for the opt-in multi-provider workforce."""
import asyncio
from hashlib import sha256
from types import SimpleNamespace

import pytest

from star.conductor_fleet import FleetMember, run_fleet_team
from star.desktop_core import Settings
from star.orchestration import Task, TaskPlan


class FakeCompletions:
    def __init__(self, model: str, *, delay: float = .025, error: Exception | None = None):
        self.model = model
        self.delay = delay
        self.error = error
        self.requests = []
        self.active = 0
        self.peak = 0

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(self.delay)
            if self.error:
                raise self.error
            return SimpleNamespace(
                model=self.model,
                choices=[SimpleNamespace(message=SimpleNamespace(content="Result from " + self.model))],
                usage=SimpleNamespace(prompt_tokens=38, completion_tokens=12),
            )
        finally:
            self.active -= 1


def transport(completions):
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def local(member_id="pc", model="local-model", project="STAR"):
    return FleetMember(member_id, Settings(provider="local", model=model, project=project))


def cloud(member_id="remote", model="demo/worker", project="STAR"):
    return FleetMember(member_id, Settings(provider="openrouter", model=model, project=project))


def tasks(*names):
    return TaskPlan([Task(id=name, role="research", goal="Analyze " + name) for name in names],
                    max_parallel=min(2, len(names)))


def run(coro):
    return asyncio.run(coro)


def test_disabled_by_default_and_write_permissions_never_granted():
    client = FakeCompletions("local-model")
    p = tasks("research")
    args = dict(plan=p, members=[local()], assignments={"research": "pc"},
                clients={"pc": transport(client)})
    with pytest.raises(PermissionError, match="off"):
        run(run_fleet_team(**args))
    p2 = TaskPlan([Task("edit", "ui", "Edit a project", writes=("src/App.tsx",))])
    with pytest.raises(PermissionError, match="cannot execute project writes"):
        run(run_fleet_team(p2, [local()], {"edit": "pc"}, enabled=True,
                           clients={"pc": transport(client)}))
    assert not client.requests


def test_two_real_distinct_model_requests_and_provider_receipts():
    pc = FakeCompletions("local-model", delay=.035)
    remote = FakeCompletions("demo/worker", delay=.035)
    p = TaskPlan([Task("a", "research", "Research references"),
                  Task("b", "ui", "Research a beautiful UI"),
                  Task("merge", "integration", "Synthesize results", dependencies=("a", "b"))],
                 max_parallel=2)
    events = []
    outcome = run(run_fleet_team(
        p, [local(), cloud()], {"a": "pc", "b": "remote", "merge": "pc"},
        enabled=True, allow_cloud_workers=True, allow_cloud_project_data=True,
        clients={"pc": transport(pc), "remote": transport(remote)},
        on_event=events.append,
    ))
    assert outcome.completed
    assert outcome.team.peak_concurrency == 2
    assert len(pc.requests) == 2 and len(remote.requests) == 1
    assert all("tools" not in req for req in pc.requests + remote.requests)
    assert [m["role"] for m in pc.requests[0]["messages"]] == ["system", "user"]
    assert "DEPENDENCY FINDINGS" in pc.requests[1]["messages"][1]["content"]
    assert outcome.receipts[1].provider == "openrouter"
    assert outcome.receipts[1].requested_model == "demo/worker"
    assert outcome.receipts[1].observed_model == "demo/worker"
    assert outcome.receipts[1].observed_match is True
    assert outcome.receipts[1].prompt_tokens == 38
    assert outcome.receipts[1].completion_tokens == 12
    assert outcome.receipts[1].output_sha256 == sha256(b"Result from demo/worker").hexdigest()
    assert not any(item.verified for item in outcome.receipts)
    assert any(event.get("provider") == "openrouter" for event in events)


def test_cloud_requires_two_distinct_owner_permissions_before_any_request():
    f = FakeCompletions("demo/worker")
    kwargs = dict(plan=tasks("one"), members=[cloud()], assignments={"one": "remote"},
                  enabled=True, clients={"remote": transport(f)})
    for allow_cloud, allow_context in [(False, False), (True, False), (False, True)]:
        with pytest.raises(PermissionError, match="require owner consent"):
            run(run_fleet_team(**kwargs, allow_cloud_workers=allow_cloud,
                               allow_cloud_project_data=allow_context))
    assert not f.requests


def test_explicit_model_mismatch_fails_and_blocks_synthesis_without_false_proof():
    f = FakeCompletions("other/paid-model")
    p = TaskPlan([Task("a", "research", "Research with a model"),
                  Task("merge", "integration", "Summarize research", dependencies=("a",))],
                 max_parallel=2)
    result = run(run_fleet_team(
        p, [cloud()], {"a": "remote", "merge": "remote"}, enabled=True,
        allow_cloud_workers=True, allow_cloud_project_data=True,
        clients={"remote": transport(f)},
    ))
    assert result.team.for_id("a").status == "failed"
    assert result.team.for_id("a").error == "ValueError"
    assert result.team.for_id("merge").status == "blocked"
    assert result.receipts[0].requested_model == "demo/worker"
    assert result.receipts[0].observed_model == "other/paid-model"
    assert result.receipts[0].observed_match is False
    assert result.receipts[0].output_sha256 is None
    assert result.receipts[1].input_sha256 is None
    assert len(f.requests) == 1


def test_dynamic_free_alias_shows_real_observed_model_not_a_fake_match():
    f = FakeCompletions("vendor/actual-model")
    result = run(run_fleet_team(
        tasks("one"), [cloud(model="openrouter/free")], {"one": "remote"},
        enabled=True, allow_cloud_workers=True, allow_cloud_project_data=True,
        clients={"remote": transport(f)},
    ))
    assert result.completed
    receipt = result.receipts[0]
    assert receipt.requested_model == "openrouter/free"
    assert receipt.observed_model == "vendor/actual-model"
    assert receipt.observed_match is False and not receipt.verified


def test_same_local_endpoint_cannot_overload_gpu_with_multiple_agent_names():
    f = FakeCompletions("local-model", delay=.05)
    result = run(run_fleet_team(
        tasks("one", "two"), [local("pc"), local("pc-two")],
        {"one": "pc", "two": "pc-two"}, enabled=True,
        clients={"pc": transport(f), "pc-two": transport(f)},
    ))
    assert result.completed
    assert result.team.peak_concurrency == 2  # scheduled, but inference queue is serial
    assert f.peak == 1


def test_quota_exhaustion_is_a_failure_not_success_or_hidden_fallback():
    f = FakeCompletions("local-model")
    member = FleetMember("pc", Settings(provider="local", model="local-model"), max_calls=1)
    result = run(run_fleet_team(
        tasks("one", "two"), [member], {"one": "pc", "two": "pc"},
        enabled=True, clients={"pc": transport(f)},
    ))
    assert not result.completed
    assert len(f.requests) == 1
    assert {r.status for r in result.team.results} == {"failed", "completed"}
    assert sum(item.output_sha256 is None for item in result.receipts) == 1


def test_invalid_members_routes_and_projects_fail_closed():
    a, b = local("one"), local("two", project="OTHER")
    with pytest.raises(ValueError, match="same selected project"):
        run(run_fleet_team(tasks("task"), [a, b], {"task": "one"}, enabled=True))
    with pytest.raises(ValueError, match="Unknown member"):
        run(run_fleet_team(tasks("task"), [a], {"task": "other"}, enabled=True))
    with pytest.raises(ValueError, match="exactly one"):
        run(run_fleet_team(tasks("task"), [a], {}, enabled=True))
    with pytest.raises(ValueError, match="Duplicate"):
        run(run_fleet_team(tasks("task"), [a, a], {"task": "one"}, enabled=True))
    with pytest.raises(ValueError, match="1–8"):
        FleetMember("one", a.settings, max_calls=10)
    with pytest.raises(ValueError, match="Invalid"):
        FleetMember("../evil", a.settings)


def test_runtime_errors_are_sanitized_and_never_create_completed_receipts():
    f = FakeCompletions("local-model", error=RuntimeError("SECRET-API-KEY"))
    result = run(run_fleet_team(
        tasks("one"), [local()], {"one": "pc"}, enabled=True,
        clients={"pc": transport(f)},
    ))
    assert not result.completed
    assert "SECRET" not in result.team.summary()
    assert result.team.for_id("one").error == "RuntimeError"
    assert result.receipts[0].output_sha256 is None


def test_timeout_does_not_claim_completion():
    f = FakeCompletions("local-model", delay=.5)
    result = run(run_fleet_team(
        tasks("slow"), [local()], {"slow": "pc"}, enabled=True,
        clients={"pc": transport(f)}, task_timeout=.11, total_timeout=.4,
    ))
    assert not result.completed
    assert result.team.for_id("slow").status in {"timed_out", "cancelled"}
    assert result.receipts[0].output_sha256 is None
