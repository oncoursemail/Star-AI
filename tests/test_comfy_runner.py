"""The local ComfyUI runners (star/comfy.py) against a fake ComfyUI: workflow vetting, the legacy
generate() loop and the ComfyClient error paths. No ComfyUI, GPU or network is involved."""
import json

import httpx
import pytest

import star.comfy as comfy
from star.comfy import ComfyClient, ComfyError, generate, load_workflow

JOB = "a1b2c3d4-0000-1111"


def workflow(tmp_path, nodes=None, name="flow.json"):
    nodes = nodes if nodes is not None else {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "old prompt", "clip": ["4", 1]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0]}},
    }
    path = tmp_path / name
    path.write_text(json.dumps(nodes), encoding="utf-8")
    return path


# ---------- vetting a workflow file ----------

def test_the_prompt_is_placed_in_a_copy_of_the_workflow(tmp_path):
    path = workflow(tmp_path)
    flow = load_workflow(path, prompt_text="a castle at dusk", prompt_node="6")
    assert flow["6"]["inputs"]["text"] == "a castle at dusk"
    assert json.loads(path.read_text(encoding="utf-8"))["6"]["inputs"]["text"] == "old prompt"


@pytest.mark.parametrize("nodes,error,match", [
    ({"1": {"class_type": "ExecuteShell", "inputs": {}}}, PermissionError, "Unreviewed or external workflow node 1"),
    ({"1": "not a node"}, PermissionError, "invalid"),
    ({}, ValueError, "Invalid API workflow"),
    ({"6": {"class_type": "KSampler", "inputs": {}}}, ValueError, "CLIPTextEncode"),
    ({"6": {"class_type": "CLIPTextEncode"}}, ValueError, "no inputs"),           # regression: was KeyError
])
def test_unsafe_or_malformed_workflows_are_refused(tmp_path, nodes, error, match):
    with pytest.raises(error, match=match):
        load_workflow(workflow(tmp_path, nodes), prompt_text="x", prompt_node="6")


def test_files_that_are_not_small_api_json_are_refused(tmp_path):
    other = tmp_path / "flow.txt"
    other.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="API-format JSON"):
        load_workflow(other, prompt_text="x", prompt_node="6")
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid API workflow"):
        load_workflow(tmp_path / "list.json", prompt_text="x", prompt_node="6")


@pytest.mark.parametrize("prompt", ["", "x" * 1501])
def test_prompts_must_be_1_to_1500_characters(tmp_path, prompt):
    with pytest.raises(ValueError, match="1-1500"):
        load_workflow(workflow(tmp_path), prompt_text=prompt, prompt_node="6")


# ---------- the legacy generate() loop ----------

class FakeComfyUI:
    """Answers /prompt, /history and /view like ComfyUI; history becomes ready after `ready_after` polls."""

    def __init__(self, outputs=None, *, ready_after=1, status=None, prompt_id=JOB, image=b"PNGDATA"):
        self.outputs = outputs if outputs is not None else {"9": {"images": [{"filename": "star_0001.png", "type": "output"}]}}
        self.ready_after, self.status, self.prompt_id, self.image = ready_after, status or {}, prompt_id, image
        self.requests, self.polls = [], 0

    def __call__(self, request):
        self.requests.append(request)
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": self.prompt_id})
        if request.url.path == "/history/" + JOB:
            self.polls += 1
            if self.polls < self.ready_after:
                return httpx.Response(200, json={})
            return httpx.Response(200, json={JOB: {"status": self.status, "outputs": self.outputs}})
        if request.url.path == "/view":
            return httpx.Response(200, content=self.image)
        return httpx.Response(404)


@pytest.fixture
def comfyui(monkeypatch):
    """Route generate()'s httpx client to a FakeComfyUI and make its 2 s polling instant."""
    state = {"fake": FakeComfyUI(), "clock": 0.0}
    real_client = httpx.Client

    def client(**kwargs):
        assert kwargs["trust_env"] is False
        return real_client(transport=httpx.MockTransport(lambda request: state["fake"](request)), **kwargs)

    def sleep(seconds):
        state["clock"] += seconds

    monkeypatch.setattr(comfy.httpx, "Client", client)
    monkeypatch.setattr(comfy.time, "sleep", sleep)
    monkeypatch.setattr(comfy.time, "monotonic", lambda: state["clock"])
    return state


def test_generate_queues_the_vetted_workflow_and_saves_the_pictures(tmp_path, comfyui):
    comfyui["fake"] = fake = FakeComfyUI(ready_after=3)
    images = generate(workflow(tmp_path), prompt="a castle", node_id="6", output=tmp_path / "out", port=8190)
    assert [path.name for path in images] == ["a1b2c3d4_0_star_0001.png"]
    assert images[0].read_bytes() == b"PNGDATA"
    queued = json.loads(fake.requests[0].content)
    assert fake.requests[0].url.host == "127.0.0.1" and fake.requests[0].url.port == 8190
    assert queued["prompt"]["6"]["inputs"]["text"] == "a castle" and fake.polls == 3


def test_generate_skips_outputs_that_could_escape_the_folder(tmp_path, comfyui):
    comfyui["fake"] = FakeComfyUI({"9": {"images": [
        {"filename": "../evil.png", "type": "output"},
        {"filename": "dir\\evil.png", "type": "output"},
        {"filename": "stream:hidden.png", "type": "output"},          # NTFS alternate data stream
        {"filename": "..", "type": "output"},
        {"filename": "input.png", "type": "input"},
        {"filename": "nested.png", "type": "output", "subfolder": "../../elsewhere"},
        {"filename": "rooted.png", "type": "output", "subfolder": "/abs"},
        {"filename": "ok.png", "type": "temp", "subfolder": "star"},
    ]}})
    images = generate(workflow(tmp_path), prompt="x", node_id="6", output=tmp_path / "out")
    assert [path.name for path in images] == ["a1b2c3d4_0_ok.png"]
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["a1b2c3d4_0_ok.png"]
    views = [r for r in comfyui["fake"].requests if r.url.path == "/view"]
    assert [r.url.params["filename"] for r in views] == ["ok.png"]


@pytest.mark.parametrize("fake,error,match", [
    (lambda: FakeComfyUI(status={"status_str": "error", "messages": []}), RuntimeError, "generation failed"),
    (lambda: FakeComfyUI({}, status={"completed": True}), RuntimeError, "no SaveImage output"),
    (lambda: FakeComfyUI(prompt_id="bad id!"), RuntimeError, "valid prompt ID"),
    (lambda: FakeComfyUI(image=b"x" * 25_000_001), ValueError, "25 MB"),
    (lambda: FakeComfyUI(ready_after=10_000), TimeoutError, "did not finish"),
])
def test_generate_reports_each_way_a_job_can_fail(tmp_path, comfyui, fake, error, match):
    comfyui["fake"] = fake()
    with pytest.raises(error, match=match):
        generate(workflow(tmp_path), prompt="x", node_id="6", output=tmp_path / "out", timeout_seconds=30)


def test_generate_refuses_an_invalid_port_before_reading_anything(tmp_path):
    with pytest.raises(ValueError, match="port"):
        generate(tmp_path / "missing.json", prompt="x", node_id="6", output=tmp_path / "out", port=70000)


# ---------- ComfyClient error paths ----------

def client_for(handler, **kwargs):
    return ComfyClient(8188, transport=httpx.MockTransport(handler), poll=0, **kwargs)


def test_a_comfyui_that_is_not_running_is_reported_as_such():
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)
    with client_for(refuse) as client:
        with pytest.raises(ComfyError) as caught:
            client.status()
        assert caught.value.kind == "not_running" and "127.0.0.1:8188" in str(caught.value)
        assert client.free() is False                     # best effort, never raises
        client.interrupt()


def test_a_comfyui_that_stops_answering_is_a_timeout():
    def slow(request):
        raise httpx.ReadTimeout("slow", request=request)
    with client_for(slow) as client, pytest.raises(ComfyError) as caught:
        client.status()
    assert caught.value.kind == "timeout"


def test_status_reports_version_and_graphics_memory():
    stats = {"system": {"comfyui_version": "0.39.2"},
             "devices": [{"name": "cuda:0 NVIDIA GeForce RTX 3060 Ti", "type": "cuda", "vram_total": 8 << 30, "vram_free": 6 << 30}]}
    with client_for(lambda request: httpx.Response(200, json=stats)) as client:
        assert client.status() == {"running": True, "version": "0.39.2", "device": "cuda:0 NVIDIA GeForce RTX 3060 Ti",
                                   "device_type": "cuda", "vram_total": 8 << 30, "vram_free": 6 << 30}


def test_uploads_use_fixed_safe_names_and_report_refusals():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"name": "source.png", "subfolder": "star"})

    with client_for(handler) as client:
        assert client.upload(b"png", "source.png") == "star/source.png"
        for bad in ("../x.png", "Source.PNG", "x.jpg", "a" * 41 + ".png"):
            with pytest.raises(ValueError):
                client.upload(b"png", bad)
    assert len(seen) == 1
    with client_for(lambda request: httpx.Response(500)) as client, pytest.raises(ComfyError, match="HTTP 500"):
        client.upload(b"png", "source.png")


@pytest.mark.parametrize("body,kind,match", [
    ({"node_errors": {"unet": {"errors": [{"type": "value_not_in_list",
                                           "details": "unet_name: 'flux-2-klein-4b-fp8.safetensors' not in []"}]}}},
     "model_missing", "flux-2-klein-4b-fp8.safetensors"),
    ({"node_errors": {"src_image": {"errors": [{"type": "value_not_in_list", "details": "image: 'star/source.png'"}]}}},
     "failed", "uploaded picture"),
    ({"error": {"message": "Prompt outputs failed validation"}}, "rejected", "Prompt outputs failed validation"),
    ("not json", "rejected", "HTTP 400"),
])
def test_a_rejected_workflow_says_what_to_fix(body, kind, match):
    def handler(request):
        if isinstance(body, str):
            return httpx.Response(400, content=body.encode())
        return httpx.Response(400, json=body)
    with client_for(handler) as client, pytest.raises(ComfyError) as caught:
        client.run({"x": {}})
    assert caught.value.kind == kind and match in str(caught.value)


def test_running_out_of_graphics_memory_frees_it_and_says_so():
    freed = []

    def handler(request):
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": JOB})
        if request.url.path == "/free":
            freed.append(json.loads(request.content))
            return httpx.Response(200)
        return httpx.Response(200, json={JOB: {"status": {"status_str": "error", "messages": [
            ["execution_start", {}],
            ["execution_error", {"exception_type": "torch.OutOfMemoryError",
                                 "exception_message": "CUDA out of memory", "node_type": "SamplerCustomAdvanced"}],
        ]}}})

    with client_for(handler) as client, pytest.raises(ComfyError) as caught:
        client.run({"x": {}})
    assert caught.value.kind == "out_of_memory" and freed == [{"unload_models": True, "free_memory": True}]


def test_other_failures_name_the_node_that_failed():
    def handler(request):
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": JOB})
        return httpx.Response(200, json={JOB: {"status": {"status_str": "error", "messages": [
            ["execution_error", {"exception_type": "ValueError", "exception_message": "bad size", "node_type": "VAEDecode"}]]}}})
    with client_for(handler) as client, pytest.raises(ComfyError) as caught:
        client.run({"x": {}})
    assert caught.value.kind == "failed" and "ValueError: bad size (in VAEDecode)" in str(caught.value)


def test_run_skips_unsafe_outputs_and_refuses_huge_pictures():
    outputs = {"out": {"images": [{"filename": "a.png", "type": "temp", "subfolder": "../up"},
                                  {"filename": "b.png", "type": "temp", "subfolder": ""}]}}

    def handler(request):
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": JOB})
        if request.url.path == "/view":
            return httpx.Response(200, content=b"y" * 25_000_001)
        return httpx.Response(200, json={JOB: {"status": {}, "outputs": outputs}})

    with client_for(handler) as client, pytest.raises(ComfyError, match="larger than 25 MB"):
        client.run({"x": {}})


def test_an_invalid_job_id_is_refused():
    with client_for(lambda request: httpx.Response(200, json={"prompt_id": 42})) as client:
        with pytest.raises(ComfyError, match="valid job id"):
            client.run({"x": {}})


def test_the_client_only_talks_to_this_computer():
    with pytest.raises(ValueError):
        ComfyClient(0)
    with pytest.raises(ValueError):
        ComfyClient(True)
    with ComfyClient(8189) as client:
        assert client.url == "http://127.0.0.1:8189"
