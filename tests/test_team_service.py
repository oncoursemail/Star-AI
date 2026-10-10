"""Real, read-only team-completion tests with a fake local model transport."""
import asyncio
from types import SimpleNamespace
from time import monotonic

import pytest

from star.team_service import specialist_plan, run_research_team
from star.learning import approve_learning


class Completions:
    def __init__(self):
        self.requests = []
        self.active = 0
        self.peak = 0

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        self.active += 1
        self.peak = max(self.active, self.peak)
        await asyncio.sleep(.025)
        self.active -= 1
        role = kwargs["messages"][0]["content"]
        label = "synthesis" if "Combine specialist observations" in role else "specialist"
        return SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(content=f"{label} result"))
        ])


def test_team_executes_four_real_model_calls_and_synthesis_waits(tmp_path):
    async def scenario():
        fake = Completions()
        client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
        phases=[]
        start=monotonic()
        result, ledger=await run_research_team(
            endpoint="http://127.0.0.1:8080/v1",
            model="star-local", project="A",
            prompt="Plan a responsive inventory UI for a Roblox game",
            home=tmp_path, client=client, parallel=2,
            on_event=phases.append,
        )
        assert "synthesis" in result
        assert ledger.completed and ledger.peak_concurrency == fake.peak == 2
        assert len(fake.requests) == 4
        assert all([x["role"] for x in req["messages"]] == ["system","user"]
                   for req in fake.requests)
        assert all("tools" not in req for req in fake.requests)
        assert "SPECIALIST FINDINGS" in fake.requests[-1]["messages"][1]["content"]
        assert len([e for e in phases if e["event"]=="agent_finished"])==4
        assert monotonic() >= start
    asyncio.run(scenario())


def test_team_uses_only_same_project_reviewed_knowledge(tmp_path):
    approve_learning(tmp_path,project="A",text="Use warm gold accents in STAR UI",
                     human_approved=True)
    approve_learning(tmp_path,project="B",text="Never use gold in another project",
                     human_approved=True)
    async def scenario():
        fake=Completions()
        client=SimpleNamespace(chat=SimpleNamespace(completions=fake))
        await run_research_team(endpoint="http://127.0.0.1:8080/v1",model="x",
            project="A",prompt="What gold UI did we approve?",home=tmp_path,client=client)
        texts=[r["messages"][1]["content"] for r in fake.requests]
        assert any("warm gold accents" in text for text in texts)
        assert all("another project" not in text for text in texts)
    asyncio.run(scenario())


def test_invalid_endpoint_or_empty_model_refused_before_network(tmp_path):
    async def scenario(endpoint, model):
        fake=Completions()
        return await run_research_team(endpoint=endpoint,model=model,project="A",
                         prompt="Check interface",home=tmp_path,
                         client=SimpleNamespace(chat=SimpleNamespace(completions=fake)))
    with pytest.raises(ValueError):
        asyncio.run(scenario("https://evil.example/v1","x"))
    with pytest.raises(ValueError):
        asyncio.run(scenario("http://127.0.0.1:8080/v1",""))
    with pytest.raises(ValueError):
        specialist_plan("x",parallel=5)


def test_team_refuses_to_declare_success_when_one_peer_fails(tmp_path):
    class FailCompletions(Completions):
        async def create(self, **kwargs):
            if "SPECIALTY: Suggest" in kwargs["messages"][0]["content"]:
                raise RuntimeError("secret api key: untrusted output")
            return await super().create(**kwargs)
    async def scenario():
        fake=FailCompletions()
        client=SimpleNamespace(chat=SimpleNamespace(completions=fake))
        return await run_research_team(endpoint="http://127.0.0.1:8080/v1",
            model="local",project="A",prompt="Build a Roblox map",
            home=tmp_path,client=client)
    with pytest.raises(RuntimeError,match="could not finish") as exc:
        asyncio.run(scenario())
    assert "api key" not in str(exc.value)
