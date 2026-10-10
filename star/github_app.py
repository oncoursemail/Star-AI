"""GitHub App installation authentication and developer-branch publishing.

Requires one-time creation/installation by GitHub account owner. NEVER commits key.
No direct main-branch changes, no PR merges, no workflow edits.
"""
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import httpx
import jwt

from .version import REPO

BRANCH = re.compile(r"^star/[a-z0-9][a-z0-9._-]{0,49}$")
SAFE_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def valid_upload_path(path: str) -> bool:
    """Source-only allowlist. Excludes local memory, secrets and CI policies."""
    if path.startswith(("star/", "docs/", "tests/")) or path in {"README.md", "requirements.txt", "pyproject.toml"}:
        suffix = path.rsplit("/", 1)[-1]
        if ".." in path.split("/") or suffix.startswith(".") or "\\" in path:
            return False
        return suffix.endswith((".py", ".md", ".toml", ".txt"))
    return False


class GitHubApp:
    def __init__(self, app_id: str, installation_id: str, key_file: Path, repo: str):
        if not (app_id.isdigit() and installation_id.isdigit() and SAFE_REPO.fullmatch(repo)):
            raise ValueError("GitHub App config requires numeric IDs and owner/repo")
        if not key_file.is_file():
            raise ValueError("GitHub App private key is missing")
        if key_file.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
            raise ValueError("GitHub App private key must be outside the project repository")
        self.repo = repo
        self.app_id = app_id
        self.installation_id = installation_id
        self.key_file = key_file
        self.token = ""
        self.token_expires = 0.0

    async def _install_token(self):
        if self.token and time.time() + 120 < self.token_expires:
            return self.token
        now = int(time.time())
        assertion = jwt.encode({"iat": now - 60, "exp": now + 540, "iss": self.app_id},
                               self.key_file.read_text(encoding="utf-8"), algorithm="RS256")
        async with httpx.AsyncClient(timeout=30) as client:
            # Request an additional per-token restriction to just this repository.
            # App installation itself must also be limited to selected repositories.
            response = await client.post(f"https://api.github.com/app/installations/{self.installation_id}/access_tokens",
                                         headers={"Authorization": f"Bearer {assertion}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
                                         json={"repositories": [self.repo.split("/", 1)[1]],
                                               "permissions": {"contents": "write", "pull_requests": "write"}})
            response.raise_for_status()
            info = response.json()
        self.token = info["token"]
        from datetime import datetime
        expiry = info.get("expires_at")
        self.token_expires = (datetime.fromisoformat(expiry.replace("Z", "+00:00")).timestamp()
                              if expiry else time.time() + 3000)
        return self.token

    async def request(self, method: str, path: str, **kwargs):
        token = await self._install_token()
        async with httpx.AsyncClient(timeout=40) as client:
            response = await client.request(method, "https://api.github.com" + path,
                                            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}, **kwargs)
        if response.status_code >= 400:
            # Avoid echoing secret-bearing responses and arbitrary internal details.
            raise RuntimeError(f"GitHub returned HTTP {response.status_code} for {method} {path}")
        return response.json() if response.content else {}

    async def check(self):
        return await self.request("GET", "/installation/repositories?per_page=100")

    async def create_branch(self, name: str):
        if self.repo != REPO:
            raise PermissionError('STAR GitHub App can modify only the canonical public STAR source repository')
        if not BRANCH.fullmatch(name):
            raise ValueError("Only names star/<safe-name> are permitted")
        repo = quote(self.repo, safe="/")
        info = await self.request("GET", f"/repos/{repo}")
        base = info["default_branch"]
        ref = await self.request("GET", f"/repos/{repo}/git/ref/heads/{quote(base, safe='')}")
        await self.request("POST", f"/repos/{repo}/git/refs", json={"ref": "refs/heads/" + name, "sha": ref["object"]["sha"]})
        return base

    async def write_branch_file(self, branch: str, path: str, raw: bytes, message: str):
        if self.repo != REPO:
            raise PermissionError('STAR GitHub App cannot upload source to a non-STAR repository')
        if not BRANCH.fullmatch(branch) or not valid_upload_path(path):
            raise ValueError("Branch or file outside STAR's allowed write scope")
        if len(raw) > 300_000:
            raise ValueError("Text file is too large for this starter")
        import base64
        endpoint = f"/repos/{quote(self.repo, safe='/')}/contents/{quote(path, safe='/')}"
        # Fetch current revision if file exists. Never overwrite a file without its SHA.
        sha = None
        try:
            existing = await self.request("GET", endpoint, params={"ref": branch})
            sha = existing.get("sha")
        except RuntimeError as exc:
            if "HTTP 404" not in str(exc):
                raise
        payload = {"message": message, "content": base64.b64encode(raw).decode("ascii"), "branch": branch}
        if sha:
            payload["sha"] = sha
        return await self.request("PUT", endpoint, json=payload)

    async def open_pr(self, base: str, head: str, title: str, body: str):
        if self.repo != REPO:
            raise PermissionError('STAR GitHub App cannot open development PRs outside the STAR source repository')
        if not BRANCH.fullmatch(head):
            raise ValueError("Not a STAR work branch")
        return await self.request("POST", f"/repos/{quote(self.repo, safe='/')}/pulls",
                                  json={"title": title[:200], "body": body[:10000], "base": base, "head": head, "draft": True})


def from_env() -> GitHubApp:
    key = os.environ.get("STAR_GITHUB_PRIVATE_KEY_FILE", "")
    if not key:
        raise ValueError("Configure STAR_GITHUB_PRIVATE_KEY_FILE outside the repository")
    return GitHubApp(os.environ.get("STAR_GITHUB_APP_ID", ""),
                     os.environ.get("STAR_GITHUB_INSTALLATION_ID", ""), Path(key).expanduser(),
                     os.environ.get("STAR_GITHUB_REPO", ""))
