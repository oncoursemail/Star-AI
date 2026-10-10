"""Fast Brain cancellation and GitHub tool permission boundaries."""
import asyncio
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import pytest
from star.agent import execute
from star.comfy import generate
from star.react_shell import ALLOWED_ACTIONS

def call(name, args):
    return SimpleNamespace(id="t1",function=SimpleNamespace(name=name,arguments=json.dumps(args)))

def reply(content=None,calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content,tool_calls=calls))])

class FakeClient:
    def __init__(self,responses):
        self.responses=list(responses)
        self.requests=[]
        self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
    async def create(self,**kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)

def test_git_read_cannot_execute_without_opt_in():
    model=FakeClient([reply(calls=[call("star_github_read",{"path":"star/agent.py"})]),
                      reply("This request was not authorized")])
    answer,messages,_=asyncio.run(execute(client=model,model="fake",prompt="Read source",image_paths=[],
                                          github_enabled=False))
    assert "not authorized" in answer
    assert any("Tool request rejected" in str(m.get("content")) for m in messages)
    assert model.requests[0].get("tools") is None

def test_github_functions_available_only_with_opt_in():
    model=FakeClient([reply("Ready")])
    asyncio.run(execute(client=model,model="fake",prompt="Read STAR source",image_paths=[],
                        github_enabled=True))
    declared={v["function"]["name"] for v in model.requests[0]["tools"]}
    assert {"star_github_read","star_github_tree"}<=declared

def test_stop_is_only_explicit_non_shell_desktop_action():
    assert "cancelMessage" in ALLOWED_ACTIONS
    assert "executeShell" not in ALLOWED_ACTIONS

def test_cancel_local_image_poll(monkeypatch,tmp_path):
    flow=tmp_path/"workflow.json"
    flow.write_text(json.dumps({"6":{"class_type":"CLIPTextEncode","inputs":{"text":"old"}}}))
    flag=Event();flag.set()
    class Result:
        def raise_for_status(self):pass
        def json(self):return {"prompt_id":"12345678-abcd-efgh"}
    class Client:
        def __init__(self,*a,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def post(self,*a,**kw):return Result()
        def get(self,*a,**kw):raise AssertionError("Cancellation should happen before polling")
    monkeypatch.setattr("star.comfy.httpx.Client",Client)
    with pytest.raises(RuntimeError,match="cancelled"):
        generate(flow,prompt="test",node_id="6",output=tmp_path/"outputs",cancel_event=flag)
