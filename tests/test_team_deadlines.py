"""Deterministic provider-speed and deadline tests; no network or GPU required."""
import asyncio
from types import SimpleNamespace

import pytest

from star.desktop_core import Settings
from star.team_deadlines import DeadlinePolicy, ProviderSpeeds, collect_text


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeProvider:
    def __init__(self, tokens_per_second, clock):
        self.rate = tokens_per_second
        self.clock = clock
        self.requests = []
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        assert kwargs["stream"] is True
        assert kwargs["max_tokens"] == 850

        async def generate():
            self.clock.advance(3)  # a measured time-to-first-token prefill
            for _ in range(100):
                self.clock.advance(1 / self.rate)
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="x"))])
            yield SimpleNamespace(choices=[], usage=SimpleNamespace(completion_tokens=100))

        return generate()


@pytest.mark.parametrize("tokens_per_second", [5, 10, 60])
def test_fake_clock_and_provider_measure_actual_generation_rate(tokens_per_second):
    clock = FakeClock()
    speeds = ProviderSpeeds(clock=clock)
    provider = FakeProvider(tokens_per_second, clock)
    key = ("test-provider", str(tokens_per_second), "model")
    partial = []
    answer = asyncio.run(collect_text(
        provider, model="model", messages=[{"role": "user", "content": "Analyze"}],
        max_tokens=850, speeds=speeds, speed_key=key, on_partial=partial.append,
    ))
    assert answer == "x" * 100
    assert partial[-1] == answer
    assert len(provider.requests) == 1
    assert speeds.get(key) == pytest.approx(tokens_per_second * 100 / 99, rel=.001)
    assert DeadlinePolicy().stage_seconds(850, speeds.get(key)) == pytest.approx(
        20 + 850 / (tokens_per_second * 100 / 99) * 1.5)
    assert speeds.get(("different-provider", "model")) is None


def test_fallback_clamps_and_invalid_samples_are_safe():
    defaults = DeadlinePolicy()
    assert defaults.stage_seconds(850) == 275
    assert defaults.stage_seconds(1400) == 440
    assert defaults.stage_seconds(850, float("nan")) == 275
    assert defaults.stage_seconds(850, 0) == 275
    assert defaults.overall_seconds(850, 1400, 2) == 1020
    assert defaults.overall_seconds(850, 1400, 1) == 1295
    bounded = DeadlinePolicy(min_seconds=40, max_seconds=90)
    assert bounded.stage_seconds(850, 60) == 41.25
    assert bounded.stage_seconds(850, 5) == 90
    assert bounded.stage_seconds(850, 1000) == 40
    clock = FakeClock()
    speeds = ProviderSpeeds(clock=clock)
    key = ("local", "model")
    for tokens, seconds in ((10, 5), (100, float("inf")), (100, .01)):
        speeds.observe(key, tokens, seconds)
    assert speeds.get(key) is None
    speeds.observe(key, 50, 5)
    speeds.observe(key, 100, 5)
    assert speeds.get(key) == pytest.approx(0.7 * 10 + 0.3 * 20)
    with pytest.raises(ValueError):
        DeadlinePolicy(min_seconds=100, max_seconds=20)


def test_owner_can_set_both_team_timeout_bounds(tmp_path):
    settings = Settings(team_timeout_min=45, team_timeout_max=600)
    path = tmp_path / "settings.json"
    settings.save(path)
    loaded = Settings.load(path)
    assert (loaded.team_timeout_min, loaded.team_timeout_max) == (45, 600)
    for invalid in (
        Settings(team_timeout_min=0),
        Settings(team_timeout_min=900, team_timeout_max=600),
        Settings(team_timeout_max=1801),
        Settings(team_timeout_min=True),
    ):
        with pytest.raises(ValueError, match="Team timeout"):
            invalid.validate()
