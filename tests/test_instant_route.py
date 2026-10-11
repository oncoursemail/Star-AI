"""Eligibility table: no model, network, keyring or clock required."""
import pytest

from star.instant_route import decide_instant_route


BASE = dict(prompt="What is a palindrome?", mode="fast", provider="star_server",
            enabled=True, installed=True, loaded=True, model="resident-small")


@pytest.mark.parametrize(("changes", "expected"), [
    ({}, True),
    ({"mode": "auto"}, True),
    ({"mode": "agent"}, False),
    ({"provider": "local"}, False),
    ({"provider": "groq"}, False),
    ({"enabled": False}, False),
    ({"installed": False}, False),
    ({"loaded": False}, False),
    ({"model": ""}, False),
    ({"attachments": 1}, False),
    ({"tools": True}, False),
    ({"research": True}, False),
    ({"documentation": True}, False),
    ({"deep": True}, False),
    ({"prompt": ""}, False),
    ({"prompt": "word " * 50}, False),
    ({"prompt": "How do I script an R6 character in Roblox?"}, False),
    ({"prompt": "Write a Python function to reverse a list."}, False),
    ({"prompt": "Look up the latest Roblox documentation."}, False),
    ({"prompt": "/deep What is a palindrome?"}, False),
    ({"prompt": "What is\na palindrome?"}, False),
])
def test_instant_decision_table(changes, expected):
    assert decide_instant_route(**(BASE | changes)).use_local is expected


def test_instant_decision_pure_and_stable():
    inputs = BASE | {"prompt": "Hi!"}
    assert decide_instant_route(**inputs) == decide_instant_route(**inputs)


@pytest.mark.parametrize(("field", "value"), [
    ("enabled", "true"),
    ("installed", 1),
    ("loaded", "yes"),
    ("tools", "false"),
    ("research", None),
    ("documentation", 0),
    ("deep", []),
    ("attachments", -1),
    ("attachments", "0"),
    ("model", "   "),
    ("model", 42),
])
def test_malformed_readiness_cannot_opt_into_instant(field, value):
    assert not decide_instant_route(**(BASE | {field: value})).use_local
