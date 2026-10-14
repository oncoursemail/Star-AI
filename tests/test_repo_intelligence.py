"""STAR may read approved public-source paths, never secrets or arbitrary repos."""
import asyncio
import base64

import httpx
import pytest

import star.repo_intelligence as repo
from star.repo_intelligence import validate_repo_path, PUBLIC_REPO

def test_public_repo_is_bound_to_star():
    assert PUBLIC_REPO=="oncoursemail/Star-AI"
    assert validate_repo_path("star/agent.py")=="star/agent.py"
    assert validate_repo_path("frontend/src/Desktop.tsx")=="frontend/src/Desktop.tsx"
    assert validate_repo_path("README.md")=="README.md"

@pytest.mark.parametrize("path",[
    "../secrets.txt",".env","star/../README.md","/.git/config",
    "https://evil.example/steal","star/private_token.py","star/.env",
    "installer/STAR.iss","star/model.gguf","frontend/public/star.svg",
    "star\\\\agent.py","star//agent.py"
])
def test_unreviewed_or_unsafe_repository_paths_rejected(path):
    with pytest.raises((PermissionError,ValueError)):
        validate_repo_path(path)


# ---------- the two GitHub reads, against a fake GitHub ----------


@pytest.fixture
def github(monkeypatch):
    """Route the module's httpx client to a handler; records every request."""
    state = {"requests": [], "handler": None}
    real_client = httpx.AsyncClient

    def client(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False

        def handle(request):
            state["requests"].append(request)
            return state["handler"](request)

        return real_client(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr(repo.httpx, "AsyncClient", client)
    return state


def tree(*paths, truncated=False, extra=()):
    entries = [{"path": path, "type": "blob"} for path in paths] + list(extra)
    return httpx.Response(200, json={"tree": entries, "truncated": truncated})


def test_tree_lists_only_approved_source_files(github):
    github["handler"] = lambda request: tree(
        "star/agent.py", "star/.hidden.py", "star/token_store.py", "installer/STAR.iss", "README.md",
        "frontend/src/App.tsx", "star/model.gguf", extra=[{"path": "star", "type": "tree"}, "junk"])
    result = asyncio.run(repo.repo_tree())
    assert result["paths"] == ["star/agent.py", "README.md", "frontend/src/App.tsx"]
    assert result["read_only"] is True and result["omitted_count"] == 0
    [request] = github["requests"]
    assert request.url.host == "api.github.com" and request.url.params["recursive"] == "1"
    assert request.url.path == f"/repos/{PUBLIC_REPO}/git/trees/main"
    assert "authorization" not in request.headers


def test_tree_applies_the_folder_filter_and_counts_what_it_left_out(github):
    github["handler"] = lambda request: tree(*[f"star/m{i}.py" for i in range(5)], "docs/a.md")
    result = asyncio.run(repo.repo_tree("star/", limit=3))
    assert result["paths"] == ["star/m0.py", "star/m1.py", "star/m2.py"] and result["omitted_count"] == 2


def test_an_incomplete_tree_is_not_presented_as_the_file_list(github):
    github["handler"] = lambda request: tree("star/agent.py", truncated=True)
    with pytest.raises(RuntimeError, match="incomplete tree"):
        asyncio.run(repo.repo_tree())


@pytest.mark.parametrize("prefix,limit", [("../", 10), ("/star", 10), ("star" + chr(92) + "x", 10), ("a" * 91, 10),
                                          ("star/", 0), ("star/", 121)])
def test_tree_refuses_bad_filters_without_asking_github(github, prefix, limit):
    with pytest.raises(ValueError):
        asyncio.run(repo.repo_tree(prefix, limit))
    assert github["requests"] == []


def test_a_redirect_is_not_followed(github):
    github["handler"] = lambda request: httpx.Response(302, headers={"location": "https://example.com/x"})
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(repo.repo_tree())
    assert len(github["requests"]) == 1


def file_reply(text, **fields):
    raw = text.encode("utf-8")
    info = {"type": "file", "encoding": "base64", "size": len(raw), "sha": "a" * 50,
            "content": base64.b64encode(raw).decode("ascii")}
    info.update(fields)
    return httpx.Response(200, json=info)


def test_read_returns_marked_untrusted_text_and_truncates_to_the_limit(github):
    github["handler"] = lambda request: file_reply("x" * 1500 + "é")
    result = asyncio.run(repo.repo_read("star/agent.py", max_chars=1000))
    assert result["content"] == "x" * 1000 and result["truncated"] is True
    assert result["untrusted_reference_only"] is True and len(result["sha"]) == 40
    assert result["source_url"] == f"https://github.com/{PUBLIC_REPO}/blob/main/star/agent.py"
    [request] = github["requests"]
    assert request.url.params["ref"] == "main"
    assert request.url.path == f"/repos/{PUBLIC_REPO}/contents/star/agent.py"
    whole = asyncio.run(repo.repo_read("star/agent.py"))
    assert whole["content"].endswith("é") and whole["truncated"] is False


@pytest.mark.parametrize("reply,error", [
    (lambda: file_reply("x", type="dir"), RuntimeError),
    (lambda: file_reply("x", encoding="none"), RuntimeError),
    (lambda: httpx.Response(200, json=["a", "list"]), RuntimeError),
    (lambda: file_reply("x", size=70000), ValueError),
    (lambda: file_reply("x", size="12"), ValueError),
    (lambda: file_reply("y" * 66000, size=10), ValueError),          # the stated size understated the content
    (lambda: httpx.Response(404, json={"message": "Not Found"}), httpx.HTTPStatusError),
])
def test_read_refuses_anything_but_a_small_base64_text_file(github, reply, error):
    github["handler"] = lambda request: reply()
    with pytest.raises(error):
        asyncio.run(repo.repo_read("star/agent.py"))


@pytest.mark.parametrize("path,limit", [("star/../.env", 18000), (".github/workflows/x.yml", 18000),
                                        ("star/agent.py", 999), ("star/agent.py", 22001)])
def test_read_validates_the_path_and_limit_before_any_request(github, path, limit):
    with pytest.raises((ValueError, PermissionError)):
        asyncio.run(repo.repo_read(path, max_chars=limit))
    assert github["requests"] == []
