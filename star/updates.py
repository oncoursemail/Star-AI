"""STAR installer updates from the single official public GitHub Releases channel.

Only the unauthenticated STAR source repository Release API is trusted.
A missing/inaccessible Release offers the browser fallback, never GitHub CLI.
Automatic installation requires the exact official Setup URL, size and SHA-256
verification from the same public GitHub API response.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from functools import total_ordering
from pathlib import Path
import hashlib
import os
import re
import shutil
import subprocess
import sys
import zipfile

import httpx

from .version import REPO, __version__

API = f'https://api.github.com/repos/{REPO}/releases/latest'
RELEASES_URL = f'https://github.com/{REPO}/releases/latest'
ASSET = 'STAR-Genesis-Windows-x64.zip'  # For compatibility with older fixtures.
MAX_INSTALLER_BYTES = 750_000_000
MIN_INSTALLER_BYTES = 1_000_000


@total_ordering
class Version:
    def __init__(self, value: str):
        match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', value)
        if not match:
            raise ValueError('Invalid STAR release version')
        self.parts = tuple(int(x) for x in match.groups())

    def __eq__(self, other):
        return self.parts == other.parts if isinstance(other, Version) else NotImplemented

    def __lt__(self, other):
        return self.parts < other.parts if isinstance(other, Version) else NotImplemented


@dataclass(frozen=True)
class UpdateResult:
    available: bool
    version: str
    url: str
    requires_browser: bool = False
    assets: tuple[dict, ...] = ()
    explanation: str = ''
    repository: str = REPO
    anonymous_access: bool = False  # The GitHub API succeeded with no account token.

    @property
    def requires_github_login(self) -> bool:
        # Compatibility for consumers of v0.5; we never require GitHub CLI.
        return self.requires_browser


@dataclass(frozen=True)
class InstallerCandidate:
    path: Path
    version: str
    checksum_verified: bool
    expected_sha256: str = ""


def _installer_name(version: str) -> str:
    Version(version)
    return f'STAR-Setup-v{version.removeprefix("v")}.exe'


def get_latest(client: httpx.Client | None = None) -> UpdateResult:
    """Check only public Star-AI Releases, without credentials or a mirror.

    Ignore untrusted release html_url fields: derive the browser URL from the
    fixed canonical repository and a syntactically validated release tag.
    """
    own = client is None
    client = client or httpx.Client(timeout=15.0, trust_env=False)
    try:
        try:
            response = client.get(API, headers={'Accept': 'application/vnd.github+json'})
            if response.status_code not in (401, 403, 404):
                response.raise_for_status()
                release = response.json()
                if isinstance(release, dict) and not (release.get('draft') or release.get('prerelease')):
                    version = Version(str(release.get('tag_name', '')))
                    assets = release.get('assets')
                    if not isinstance(assets, list):
                        raise ValueError('Release assets must be a list')
                    tag = '.'.join(str(x) for x in version.parts)
                    expected_url = f'https://github.com/{REPO}/releases/tag/v{tag}'
                    return UpdateResult(version > Version(__version__), tag, expected_url,
                        assets=tuple(assets), repository=REPO, anonymous_access=True)
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, KeyError, TypeError):
            pass
        return UpdateResult(False, __version__, RELEASES_URL, requires_browser=True,
            explanation='No public STAR Release is accessible. Open GitHub Releases in your browser to download Setup. GitHub CLI is not required.',
            repository=REPO)
    finally:
        if own:
            client.close()


def _trusted_setup_asset(result: UpdateResult) -> dict:
    if not result.available or Version(result.version) <= Version(__version__):
        raise ValueError('No newer STAR version is available')
    if result.repository != REPO or not result.anonymous_access:
        raise PermissionError('Automatic updates require an anonymously accessible official STAR Release')
    name = _installer_name(result.version)
    matches = [a for a in result.assets if a.get('name') == name]
    if len(matches) != 1:
        raise ValueError('New release does not contain exactly one Windows Setup installer')
    asset = matches[0]
    digest = str(asset.get('digest') or '')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise ValueError('Release does not provide a trusted SHA-256 digest')
    url = str(asset.get('browser_download_url') or '')
    expected = f'https://github.com/{REPO}/releases/download/v{result.version}/' + name
    if url != expected:
        raise ValueError('Unexpected STAR release installer URL')
    size = int(asset.get('size') or 0)
    if not MIN_INSTALLER_BYTES <= size <= MAX_INSTALLER_BYTES:
        raise ValueError('Installer size outside allowed range')
    return asset



def stage_installer(result: UpdateResult, storage: Path,
                    client: httpx.Client | None = None,
                    progress: Callable[[int, int], None] | None = None) -> InstallerCandidate:
    """Download a SHA-256 checked installer from the official public Release.

    If release metadata becomes unavailable, automatic installation is
    refused and the user is offered the official browser fallback.
    """
    if sys.platform != 'win32':
        raise OSError('STAR installer downloads run on Windows only')
    asset = _trusted_setup_asset(result)
    path = storage.resolve() / 'updates' / f'v{result.version}' / asset['name']
    path.parent.mkdir(parents=True, exist_ok=True)
    expected = asset['digest'].split(':', 1)[1]
    if path.is_file() and _sha256(path) == expected:
        if progress:
            progress(int(asset['size']), int(asset['size']))
        return InstallerCandidate(path, result.version, checksum_verified=True, expected_sha256=expected)

    own = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(30, read=90), trust_env=False)
    temp = path.with_suffix('.exe.part')
    try:
        digest = hashlib.sha256()
        count = 0
        with client.stream('GET', asset['browser_download_url'], follow_redirects=True) as response:
            if response.status_code in (401, 403, 404):
                raise PermissionError('The release is private. Open it in your browser and select the downloaded Setup installer.')
            response.raise_for_status()
            if response.url.scheme != 'https':
                raise PermissionError('Installer download was redirected to a non-HTTPS address')
            with temp.open('wb') as output:
                for chunk in response.iter_bytes(1024 * 1024):
                    if not chunk:
                        continue
                    count += len(chunk)
                    if count > MAX_INSTALLER_BYTES or count > int(asset['size']):
                        raise ValueError('Installer exceeds trusted release size')
                    digest.update(chunk)
                    output.write(chunk)
                    if progress:
                        progress(count, int(asset['size']))
        if count != int(asset['size']) or digest.hexdigest() != expected:
            raise ValueError('Release installer failed size or SHA-256 verification')
        os.replace(temp, path)
        return InstallerCandidate(path, result.version, checksum_verified=True, expected_sha256=expected)
    finally:
        temp.unlink(missing_ok=True)
        if own:
            client.close()


def _sha256(path: Path) -> str:
    with path.open('rb') as fd:
        return hashlib.file_digest(fd, 'sha256').hexdigest()


def select_downloaded_installer(path: Path) -> InstallerCandidate:
    """Inspect an explicitly selected GitHub Setup download before executing it.

    Without authenticated release metadata, an unsigned manually selected EXE
    cannot be cryptographically authenticated by filename alone. The UI must
    explicitly disclose that limitation and ask before launching.
    """
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError('Choose a downloaded Setup executable')
    match = re.fullmatch(r'STAR-Setup-v(\d+\.\d+\.\d+)\.exe', path.name, flags=re.IGNORECASE)
    if not match:
        raise ValueError('Choose STAR-Setup-vX.Y.Z.exe from your STAR GitHub Releases page')
    version = match.group(1)
    if Version(version) <= Version(__version__):
        raise ValueError(f'That installer (v{version}) is not newer than STAR v{__version__}')
    if not MIN_INSTALLER_BYTES <= path.stat().st_size <= MAX_INSTALLER_BYTES:
        raise ValueError('Downloaded Setup file has an unexpected size')
    with path.open('rb') as fd:
        if fd.read(2) != b'MZ':
            raise ValueError('Selected file is not a Windows executable')
    sums = path.parent / 'SHA256SUMS.txt'
    verified = False
    if sums.is_file() and sums.stat().st_size <= 128_000:
        checksum_lines = sums.read_text(encoding='utf-8-sig', errors='replace').splitlines()
        for line in checksum_lines:
            match_sum = re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?(.+)', line.strip())
            if match_sum and match_sum.group(2) == path.name:
                if _sha256(path) != match_sum.group(1).lower():
                    raise ValueError('Setup checksum does not match downloaded SHA256SUMS.txt')
                verified = True
                break
    return InstallerCandidate(path, version, checksum_verified=verified)


def launch_installer(candidate: InstallerCandidate, *, unattended: bool = False) -> None:
    """Run a user-approved Inno Setup installer, optionally without another wizard.

    Unattended mode requires a GitHub-checksummed, automatically downloaded
    candidate. It shows installation progress and errors; no shell is invoked.
    """
    if sys.platform != 'win32':
        raise OSError('STAR installers run on Windows only')
    # Recheck the selected file and ensure it hasn't been substituted after the
    # dialogue; the path is explicitly user-selected and never model-generated.
    checked = select_downloaded_installer(candidate.path)
    if checked.version != candidate.version:
        raise ValueError('Installer changed since selection')
    if candidate.expected_sha256 and _sha256(checked.path) != candidate.expected_sha256:
        raise ValueError('Staged installer changed after SHA-256 verification')
    if unattended and (not candidate.checksum_verified or not candidate.expected_sha256):
        raise PermissionError('Unattended upgrades require a verified GitHub Release SHA-256')
    arguments = [str(checked.path)]
    if unattended:
        # Inno Setup handles closing old app files and launching the new STAR.
        arguments += ['/SILENT', '/CLOSEAPPLICATIONS', '/NORESTART']
    subprocess.Popen(arguments, cwd=str(checked.path.parent),
                     stdin=subprocess.DEVNULL, shell=False, close_fds=True,
                     creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))


# Compatibility helpers for verification fixtures from STAR Genesis v0.5.
def _verify_asset(path: Path, assets: tuple[dict, ...]):
    matches = [a for a in assets if a.get('name') == ASSET]
    if len(matches) != 1:
        raise ValueError('Release does not have exactly one Windows portable package')
    digest = str(matches[0].get('digest') or '')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
        raise ValueError('Release is missing its trusted SHA-256 manifest')
    if _sha256(path) != digest.partition(':')[2]:
        raise ValueError('Release checksum mismatch. Upgrade stopped.')


def _extract_update(archive: Path, target: Path):
    """Legacy ZIP validation retained only for existing regression fixtures."""
    target.mkdir(parents=True, exist_ok=True)
    total = 0
    with zipfile.ZipFile(archive) as z:
        if len(z.infolist()) > 5000:
            raise ValueError('Release contains too many files')
        for info in z.infolist():
            name = info.filename.replace('\\', '/')
            parts = name.strip('/').split('/')
            if not name or name.startswith('/') or ':' in parts[0] or any(p in ('.', '..') for p in parts):
                raise ValueError('Unsafe release ZIP entry')
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Release contains a symbolic link')
            total += info.file_size
            if total > 2_000_000_000:
                raise ValueError('Unpacked release exceeds 2 GB')
            if info.is_dir():
                continue
            dst = target.joinpath(*parts)
            dst.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, dst.open('wb') as output:
                shutil.copyfileobj(src, output)
    if not (target / 'STAR.exe').is_file():
        raise ValueError('Release package is missing STAR.exe')


def prune_obsolete_update_packages(storage: Path, current_version: str = __version__) -> list[str]:
    """Remove obsolete *downloaded installers only*, never projects/models/chats.

    The currently installed version is retained as a possible repair copy.
    Reject symbolic links and folders without STAR version names.
    """
    root = storage.resolve() / 'updates'
    if not root.is_dir() or root.is_symlink():
        return []
    current = Version(current_version)
    removed = []
    for path in root.iterdir():
        if path.is_symlink() or not path.is_dir() or not re.fullmatch(r'v\d+\.\d+\.\d+', path.name):
            continue
        if Version(path.name) >= current:
            continue
        shutil.rmtree(path)
        removed.append(path.name)
    return removed
