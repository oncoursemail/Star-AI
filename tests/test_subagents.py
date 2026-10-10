"""Delegation is read-only, bounded, and clearly unverified."""
import asyncio
from types import SimpleNamespace
import pytest
from star.subagents import delegate

class Stub:
    def __init__(self):
        self.calls=0
        self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
    async def create(self,**kwargs):
        self.calls+=1
        assert "tools" not in kwargs
        assert [m["role"] for m in kwargs["messages"]]==["system","user"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Draft answer"))])

def test_delegate_does_not_execute_tools():
    stub=Stub()
    result=asyncio.run(delegate(stub,"test-model",["Research first angle","Review second angle"],parallelism=2))
    assert stub.calls==2
    assert all(v["verified"] is False and v["draft"]=="Draft answer" for v in result)

def test_delegate_rejects_massive_fanout():
    stub=Stub()
    with pytest.raises(ValueError):
        asyncio.run(delegate(stub,"model",["a"]*20))
    with pytest.raises(ValueError):
        asyncio.run(delegate(stub,"model",["first topic","second topic"],parallelism=9))
