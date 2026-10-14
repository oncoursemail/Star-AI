"""Delegated specialists keep partial streams incomplete, with no tool privileges."""
import asyncio
from types import SimpleNamespace

from star.specialist_agents import ResearchTeam


class StalledModel:
    def __init__(self):
        self.requests = []
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        assert kwargs["stream"] is True
        assert "tools" not in kwargs

        async def chunks():
            yield SimpleNamespace(choices=[
                SimpleNamespace(delta=SimpleNamespace(content="Draft evidence, unfinished"))
            ])
            await asyncio.sleep(30)

        return chunks()


def test_delegated_team_retains_partial_and_blocks_dependent_stage():
    async def scenario():
        provider = StalledModel()
        team = ResearchTeam(client=provider, model="small-local", project="Test",
                            parallelism=2, timeout_min=.12, timeout_max=.12)
        output = await team.run([
            {"id": "research", "role": "research", "goal": "Analyze local architecture"},
            {"id": "review", "role": "review", "goal": "Review the research",
             "dependencies": ["research"]},
        ])
        assert len(provider.requests) == 1
        assert output["model_calls"] == 1
        assert output["reports"][0]["status"] == "incomplete"
        assert output["reports"][0]["analysis"] == "Draft evidence, unfinished"
        assert "INCOMPLETE" in output["reports"][0]["notice"]
        assert output["reports"][1]["status"] == "blocked"

    asyncio.run(scenario())


def test_failed_specialist_does_not_starve_independent_work():
    class FailureThenSuccess:
        def __init__(self):
            self.calls = 0
            self.chat = SimpleNamespace(completions=self)

        async def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("First specialist is unavailable")

            async def chunks():
                yield SimpleNamespace(choices=[
                    SimpleNamespace(delta=SimpleNamespace(content="Independent finding"))
                ])
            return chunks()

    async def scenario():
        provider = FailureThenSuccess()
        team = ResearchTeam(client=provider, model="small-local", project="Test",
                            parallelism=1)
        output = await team.run([
            {"id": "first", "role": "research", "goal": "Independent first topic"},
            {"id": "second", "role": "review", "goal": "Independent second topic"},
        ])
        assert provider.calls == 2
        assert [record["status"] for record in output["reports"]] == [
            "failed", "completed",
        ]
        assert output["reports"][1]["analysis"] == "Independent finding"

    asyncio.run(scenario())
