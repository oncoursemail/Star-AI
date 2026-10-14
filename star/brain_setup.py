"""Verified, resumable STAR Brain installation for Windows 11.

The official llama.cpp stable release currently contains *no* Windows binaries.
Official numbered builds (bXXXXX) do, and are published as GitHub prereleases.
Only a Windows x64 Vulkan ZIP with an upstream SHA-256 digest is accepted.

Model and projector are downloaded directly from a fixed Hugging Face revision,
with separately recorded publisher SHA-256 checksums. No external model server
or paid inference API is required.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile

import httpx

from .version import __version__

ENGINE_RELEASE = 'https://api.github.com/repos/ggml-org/llama.cpp/releases/latest'
ENGINE_BUILDS = 'https://api.github.com/repos/ggml-org/llama.cpp/releases'
ENGINE_FALLBACK_TAG = 'b11429'  # Verified by inspection of the official GitHub release API.
ENGINE_FALLBACK_SHA = '1bfe78ad9168b79fa02bf67f6af9f5e17a966d824d77238517f7bef12ac73b36'
MODEL_REPO = 'lmstudio-community/Qwen3.5-4B-GGUF'
MODEL_REVISION = 'f9f88ac3e234be915e23811a6d28ea287bdb927e'
MODEL_FILES = ('Qwen3.5-4B-Q4_K_M.gguf', 'mmproj-Qwen3.5-4B-BF16.gguf')
MODEL_SHAS = {
    MODEL_FILES[0]: '25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c',
    MODEL_FILES[1]: 'ae08d9d7eceb8f2d0672d61b5e6aa78b611f2942b55ed71d21414980cc454b91',
}
MODEL_SIZES = {MODEL_FILES[0]: 2_707_513_696, MODEL_FILES[1]: 675_900_000}
MODEL_TREE = f'https://huggingface.co/api/models/{MODEL_REPO}/tree/main?expand=true'
MODEL_URL = f'https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/'
USER_AGENT = f'STAR-Intelligence/{__version__} (Local installation)'
CHUNK = 1024 * 1024
MAX_ENGINE_ARCHIVE = 1_500_000_000
MAX_UNPACKED_ENGINE = 2_000_000_000
MAX_MODEL_BYTES = 8_000_000_000
MIN_FREE_BYTES = 4_300_000_000


@dataclass(frozen=True)
class BrainInstall:
    executable: str
    model: str
    projector: str
    engine_version: str
    model_repo: str = MODEL_REPO

    @classmethod
    def load(cls, state: Path):
        if not state.is_file():
            return None
        try:
            data = json.loads(state.read_text(encoding='utf-8'))
            result = cls(**data)
            for item in (result.executable, result.model, result.projector):
                if not Path(item).is_file():
                    return None
            return result
        except (OSError, ValueError, TypeError):
            return None


def _hex_sha256(raw: str) -> str:
    sha = str(raw or '').removeprefix('sha256:').strip().lower()
    if not re.fullmatch(r'[0-9a-f]{64}', sha):
        raise ValueError('The publisher did not provide a usable SHA-256 checksum')
    return sha


def _model_shas(tree: list[dict]) -> dict[str, str]:
    """Legacy HF metadata validation, retained for compatibility and testing."""
    files = {}
    for entry in tree:
        name = entry.get('path', '')
        if name in MODEL_FILES:
            lfs = entry.get('lfs') or {}
            files[name] = _hex_sha256(lfs.get('oid') or lfs.get('sha256') or '')
    if set(files) != set(MODEL_FILES):
        raise ValueError('Could not verify both model and vision projector hashes')
    return files


def _engine_asset(release: dict) -> dict:
    """Only trusted numbered builds or a full stable release with verified digest."""
    if release.get('draft'):
        raise ValueError('Draft engine releases are not accepted')
    tag = str(release.get('tag_name', ''))
    if release.get('prerelease') and not re.fullmatch(r'b\d+', tag):
        raise ValueError('Only official numbered llama.cpp build prereleases are accepted')
    matches = [asset for asset in release.get('assets', [])
               if re.fullmatch(r'llama-b\d+-bin-win-vulkan-x64\.zip', str(asset.get('name', '')))]
    if len(matches) != 1:
        raise ValueError('This llama.cpp release has no Windows Vulkan executable')
    asset = matches[0]
    _hex_sha256(asset.get('digest', ''))
    url = str(asset.get('browser_download_url', ''))
    prefix = 'https://github.com/ggml-org/llama.cpp/releases/download/'
    if not url.startswith(prefix) or not url.endswith('/' + asset['name']):
        raise ValueError('Unexpected engine distribution URL')
    if tag and url.removeprefix(prefix).split('/')[0] != tag:
        raise ValueError('Engine download does not match its release tag')
    return asset


def _fallback_engine_release() -> tuple[dict, dict]:
    asset_name = f'llama-{ENGINE_FALLBACK_TAG}-bin-win-vulkan-x64.zip'
    release = {'tag_name': ENGINE_FALLBACK_TAG, 'prerelease': True, 'draft': False,
               'assets': [{'name': asset_name, 'size': 33_337_769,
                           'digest': 'sha256:' + ENGINE_FALLBACK_SHA,
                           'browser_download_url': 'https://github.com/ggml-org/llama.cpp/releases/download/'
                           + ENGINE_FALLBACK_TAG + '/' + asset_name}]}
    return release, _engine_asset(release)


def _select_engine_release(client: httpx.Client, callback: Callable[[dict], None]) -> tuple[dict, dict]:
    """Ignore the GitHub stable-pointer-only release; select an official numbered binary build.

    A known/pinned, upstream-hashed build is the offline metadata fallback.
    The downloaded archive must still match its SHA-256 before extraction.
    """
    callback({'phase': 'Finding the official Windows AI engine'})
    try:
        latest = client.get(ENGINE_RELEASE)
        latest.raise_for_status()
        release = latest.json()
        try:
            return release, _engine_asset(release)
        except ValueError:
            callback({'phase': 'The stable release contains no Windows app; looking for official builds'})
        for page in (1, 2):
            result = client.get(ENGINE_BUILDS, params={'per_page': 30, 'page': page})
            result.raise_for_status()
            for candidate in result.json():
                if not re.fullmatch(r'b\d+', str(candidate.get('tag_name', ''))):
                    continue
                try:
                    return candidate, _engine_asset(candidate)
                except ValueError:
                    continue
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        callback({'phase': 'GitHub metadata unavailable; using a checksum-pinned official build'})
    callback({'phase': 'Using a known official Windows Vulkan build'})
    return _fallback_engine_release()


def _file_hash(path: Path) -> str:
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def _download_verified(client: httpx.Client, url: str, path: Path,
                       expected_sha: str, maximum: int, callback: Callable[[dict], None], stage: str):
    """Stream, optionally resume with HTTP 206, and verify before replacing destination."""
    expected = _hex_sha256(expected_sha)
    if not url.startswith(('https://github.com/', 'https://objects.githubusercontent.com/',
                           'https://huggingface.co/')):
        raise PermissionError('Unapproved download origin')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and _file_hash(path) == expected:
        callback({'phase': stage, 'downloaded': path.stat().st_size,
                  'total': path.stat().st_size, 'finished': True})
        return
    temporary = path.with_suffix(path.suffix + '.part')
    # The connection can drop after receiving the final byte but before the
    # download is promoted. In that case no Range request should be needed.
    if temporary.is_file() and _file_hash(temporary) == expected:
        os.replace(temporary, path)
        callback({'phase': stage, 'downloaded': path.stat().st_size,
                  'total': path.stat().st_size, 'finished': True})
        return
    offset = temporary.stat().st_size if temporary.is_file() else 0
    if offset > maximum:
        temporary.unlink()
        offset = 0
    headers = {'Range': f'bytes={offset}-'} if offset else {}
    try:
        with client.stream('GET', url, follow_redirects=True, headers=headers) as response:
            response.raise_for_status()
            if response.url.scheme != 'https':
                raise PermissionError('Refusing redirected non-HTTPS download')
            accepted_range = offset > 0 and getattr(response, 'status_code', 200) == 206
            range_start = str(response.headers.get('content-range', ''))
            if accepted_range and not range_start.startswith(f'bytes {offset}-'):
                raise ValueError('Server returned a mismatched resume range')
            if offset and not accepted_range:
                offset = 0  # Server ignored Range; begin a fresh verified download.
            declared = int(response.headers.get('content-length', '0'))
            if declared + offset > maximum:
                raise ValueError(f'{stage} exceeds maximum download size')
            digest = hashlib.sha256()
            if offset:
                with temporary.open('rb') as prior:
                    for block in iter(lambda: prior.read(CHUNK), b''):
                        digest.update(block)
            count = offset
            with temporary.open('ab' if offset else 'wb') as output:
                for block in response.iter_bytes(CHUNK):
                    if not block:
                        continue
                    count += len(block)
                    if count > maximum:
                        raise ValueError(f'{stage} exceeds maximum download size')
                    digest.update(block)
                    output.write(block)
                    callback({'phase': stage, 'downloaded': count, 'total': declared + offset or 0})
        if digest.hexdigest() != expected:
            temporary.unlink(missing_ok=True)
            raise ValueError(f'{stage} failed checksum verification. Please try again.')
        os.replace(temporary, path)
        callback({'phase': stage, 'downloaded': count, 'total': count, 'finished': True})
    except (httpx.HTTPError, OSError):
        # Leave the .part file so an interrupted multi-gigabyte download can resume.
        raise


def _safe_extract(source: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            name = info.filename.replace('\\', '/')
            parts = name.split('/')
            if info.is_dir() and parts[-1] == '':
                parts.pop()
            if (not name or name.startswith('/') or not parts or any(part in ('.', '..', '') for part in parts)
                    or ':' in parts[0] or info.file_size > MAX_UNPACKED_ENGINE):
                raise ValueError('Unsafe upstream archive entry')
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Archive contains a symlink')
            total += info.file_size
            if total > MAX_UNPACKED_ENGINE:
                raise ValueError('Upstream archive exceeds extraction budget')
            if info.is_dir():
                continue
            target = destination.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst, CHUNK)
    found = list(destination.rglob('llama-server.exe'))
    if len(found) != 1:
        raise ValueError('The official Windows archive did not contain llama-server.exe')
    return found[0]


def install_brain(home: Path, progress: Callable[[dict], None] | None = None,
                  client: httpx.Client | None = None) -> BrainInstall:
    """Called by user action. Fetches ~3.5 GB and preserves verified partial downloads."""
    if sys.platform != 'win32':
        raise OSError('STAR Brain installation currently supports Windows 11 only')
    callback = progress or (lambda _: None)
    home = home.resolve()
    state = home / 'brain.json'
    existing = BrainInstall.load(state)
    if existing:
        callback({'phase': 'ready', 'finished': True, 'overall_downloaded': 1, 'overall_total': 1})
        return existing
    home.mkdir(parents=True, exist_ok=True)
    owns_client = client is None
    client = client or httpx.Client(headers={'User-Agent': USER_AGENT}, timeout=httpx.Timeout(45, read=120))
    try:
        release, asset = _select_engine_release(client, callback)
        required = int(asset.get('size') or 40_000_000) + sum(MODEL_SIZES.values())
        # Disk availability is checked before transferring gigabytes. Existing files
        # can make the actual required free space lower, so allow a retry after cleanup.
        if shutil.disk_usage(home).free < MIN_FREE_BYTES and not state.exists():
            raise OSError('Not enough free disk space. STAR Brain needs around 4.3 GB free.')
        steps = [('Downloading STAR engine', required - sum(MODEL_SIZES.values())),
                 *[('Downloading ' + name, MODEL_SIZES[name]) for name in MODEL_FILES]]
        overall = sum(x[1] for x in steps)
        completed = 0

        def report(ev):
            item = dict(ev)
            item['overall_downloaded'] = min(overall, completed + (item.get('downloaded') or 0))
            item['overall_total'] = overall
            callback(item)

        engine_dir = home / 'engines' / str(release['tag_name'])
        engine_archive = home / 'downloads' / asset['name']
        _download_verified(client, asset['browser_download_url'], engine_archive,
                           asset['digest'], MAX_ENGINE_ARCHIVE, report, steps[0][0])
        completed += steps[0][1]
        callback({'phase': 'Installing the verified engine', 'overall_downloaded': completed, 'overall_total': overall})
        executable = _safe_extract(engine_archive, engine_dir)
        model_dir = home / 'models' / 'qwen3.5-4b-q4'
        for filename in MODEL_FILES:
            dest = model_dir / filename
            _download_verified(client, MODEL_URL + filename, dest, MODEL_SHAS[filename],
                               MAX_MODEL_BYTES, report, 'Downloading ' + filename)
            completed += MODEL_SIZES[filename]
        item = BrainInstall(executable=str(executable), model=str(model_dir / MODEL_FILES[0]),
                            projector=str(model_dir / MODEL_FILES[1]), engine_version=str(release['tag_name']))
        temporary = state.with_suffix('.tmp')
        temporary.write_text(json.dumps(asdict(item), indent=2), encoding='utf-8')
        os.replace(temporary, state)
        callback({'phase': 'Verifying and starting STAR Brain', 'overall_downloaded': overall, 'overall_total': overall})
        return item
    finally:
        if owns_client:
            client.close()
