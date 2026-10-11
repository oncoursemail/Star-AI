"""Read-only source awareness for STAR's explicitly selected public repository.

This is a public GitHub REST adapter, not a substitute for GitHub App installation
permissions or a general shell/code executor. Model output never selects arbitrary
hosts, credentials, refs, private repositories, or writes.
"""
from __future__ import annotations
import base64
from pathlib import PurePosixPath
import re
from urllib.parse import quote

import httpx
from .version import REPO

PUBLIC_REPO = REPO  # The existing public STAR source repository, not downloads.
ALLOWED_EXACT = {"README.md", "AGENTS.md", "pyproject.toml", "requirements.txt"}
ALLOWED_PREFIXES = ("star/", "frontend/src/", "docs/", "tests/", "evals/")
ALLOWED_SUFFIXES = {".py", ".md", ".toml", ".txt", ".tsx", ".ts", ".json", ".css", ".yaml", ".yml"}
HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

def validate_repo_path(path: str) -> str:
    if not isinstance(path, str) or not 1 <= len(path) <= 180:
        raise ValueError("Repository path must be 1–180 characters")
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", path) or path.startswith("/") or "\\" in path:
        raise ValueError("Invalid repository path")
    parts = path.split("/")
    if any(p in ("", ".", "..") or p.startswith(".") for p in parts):
        raise ValueError("Hidden files and path traversal are not allowed")
    if path not in ALLOWED_EXACT and not path.startswith(ALLOWED_PREFIXES):
        raise PermissionError("Reading source is limited to approved STAR source/documentation paths")
    if PurePosixPath(path).suffix.lower() not in ALLOWED_SUFFIXES:
        raise PermissionError("Unsupported repository source file type")
    if any("secret" in p.lower() or "credential" in p.lower() or "token" in p.lower() for p in parts):
        raise PermissionError("Secret/credential-related source cannot be loaded into the model")
    return path

async def repo_tree(prefix: str = "", limit: int = 90) -> dict:
    if not isinstance(prefix,str) or len(prefix)>90 or prefix.startswith("/") or ".." in prefix or "\\" in prefix:
        raise ValueError("Invalid directory filter")
    if not 1 <= limit <= 120:
        raise ValueError("Maximum 120 source filenames")
    url = f"https://api.github.com/repos/{PUBLIC_REPO}/git/trees/main"
    async with httpx.AsyncClient(timeout=10.0, trust_env=False, follow_redirects=False) as client:
        response = await client.get(url,params={"recursive":"1"},headers=HEADERS)
        response.raise_for_status()
        payload = response.json()
    if payload.get("truncated"):
        raise RuntimeError("GitHub returned an incomplete tree; no verified file list")
    records = []
    for entry in payload.get("tree", []):
        if not isinstance(entry,dict) or entry.get("type") != "blob":
            continue
        path=entry.get("path")
        try:
            validate_repo_path(path)
        except (ValueError,PermissionError):
            continue
        if path.startswith(prefix):
            records.append(path)
    return {"repository": PUBLIC_REPO,"ref":"main","paths":records[:limit],
            "omitted_count":max(0,len(records)-limit),"read_only":True}

async def repo_read(path: str, *, max_chars: int = 18000) -> dict:
    path=validate_repo_path(path)
    if not 1000 <= max_chars <= 22000:
        raise ValueError("Source character limit must be 1,000–22,000")
    url = f"https://api.github.com/repos/{PUBLIC_REPO}/contents/{quote(path,safe='/')}"
    async with httpx.AsyncClient(timeout=10.0, trust_env=False, follow_redirects=False) as client:
        response = await client.get(url,params={"ref":"main"},headers=HEADERS)
        response.raise_for_status()
        info=response.json()
    if not isinstance(info,dict) or info.get("type")!="file" or info.get("encoding")!="base64":
        raise RuntimeError("GitHub did not return a file with base64 text content")
    if not isinstance(info.get("size"),int) or info["size"]>65000:
        raise ValueError("Choose a smaller source file (<65 KB)")
    raw=base64.b64decode(info.get("content", ""),validate=False)
    if len(raw)>65000:
        raise ValueError("GitHub file exceeded 65 KB")
    contents=raw.decode("utf-8")
    return {"repository":PUBLIC_REPO,"ref":"main","path":path,"sha":str(info.get("sha",""))[:40],
            "source_url":f"https://github.com/{PUBLIC_REPO}/blob/main/{quote(path,safe='/')}",
            "content":contents[:max_chars],"truncated":len(contents)>max_chars,
            "untrusted_reference_only":True,"read_only":True}
