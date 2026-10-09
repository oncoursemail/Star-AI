"""Regression suite: private STAR Releases work without GitHub CLI.

These tests use fake HTTP responses and fake EXEs. They do not contact GitHub,
execute installers, or claim real native Windows install has been verified.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import hashlib
import re
import subprocess

import pytest
from star import updates


class FakeResponse:
    def __init__(self, status_code=200, body=None, data=b''):
        self.status_code = status_code
        self.body = body or {}
        self.data = data
        self.url = SimpleNamespace(scheme='https')
    def raise_for_status(self):
        if self.status_code >= 400:
            raise ValueError(f'HTTP {self.status_code}')
    def json(self):
        return self.body
    def iter_bytes(self, n):
        yield self.data[:n]
        yield self.data[n:]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.stream_calls = []
    def get(self, *args, **kwargs):
        return self.response
    def stream(self, *args, **kwargs):
        self.stream_calls.append((args, kwargs))
        return self.response


def _fake_exe(path: Path, data: bytes | None = None):
    path.write_bytes(data if data is not None else b'MZ' + b'R' * (updates.MIN_INSTALLER_BYTES + 100))
    return path


def test_private_release_falls_back_to_browser_not_gh_cli():
    for status in [401, 403, 404]:
        result = updates.get_latest(FakeClient(FakeResponse(status)))
        assert result.requires_browser
        assert not result.available
        assert 'github.com/' in result.url
        assert 'GitHub CLI is not required' in result.explanation
    assert not hasattr(updates, '_gh')


def test_public_release_detects_new_version_and_current_version():
    body={'tag_name':'v0.8.3','html_url':updates.PUBLIC_RELEASES_URL,'assets':[]}
    result=updates.get_latest(FakeClient(FakeResponse(body=body)))
    assert result.available and not result.requires_browser and result.version=='0.8.3'
    body['tag_name']='v0.6.0'
    assert not updates.get_latest(FakeClient(FakeResponse(body=body))).available


def test_only_newer_exactly_named_manual_setup_accepted(tmp_path):
    latest=_fake_exe(tmp_path/'STAR-Setup-v0.8.3.exe')
    result=updates.select_downloaded_installer(latest)
    assert result.version=='0.8.3' and not result.checksum_verified
    with pytest.raises(ValueError, match='not newer'):
        updates.select_downloaded_installer(_fake_exe(tmp_path/'STAR-Setup-v0.6.0.exe'))
    with pytest.raises(ValueError, match='Choose STAR-Setup'):
        updates.select_downloaded_installer(_fake_exe(tmp_path/'installer.exe'))
    with pytest.raises(ValueError, match='not a Windows executable'):
        updates.select_downloaded_installer(_fake_exe(tmp_path/'STAR-Setup-v0.8.4.exe', b'XX' + b'R' * (updates.MIN_INSTALLER_BYTES+1)))


def test_optional_adjacent_sha256_manifest_verification(tmp_path):
    file=_fake_exe(tmp_path/'STAR-Setup-v0.8.3.exe')
    checksum=hashlib.sha256(file.read_bytes()).hexdigest()
    (tmp_path/'SHA256SUMS.txt').write_text(f'{checksum}  STAR-Setup-v0.8.3.exe\n')
    assert updates.select_downloaded_installer(file).checksum_verified
    (tmp_path/'SHA256SUMS.txt').write_text(f'{"f"*64}  STAR-Setup-v0.8.3.exe\n')
    with pytest.raises(ValueError, match='checksum'):
        updates.select_downloaded_installer(file)


def test_reject_untrusted_public_release_asset(tmp_path, monkeypatch):
    monkeypatch.setattr(updates.sys,'platform','win32')
    result=updates.UpdateResult(True,'0.8.3',updates.PUBLIC_RELEASES_URL,repository=updates.PUBLIC_REPO,assets=({'name': 'STAR-Setup-v0.8.3.exe','digest':'sha256:'+'a'*64,'size':15000000,'browser_download_url':'https://bad.example/install.exe'},))
    with pytest.raises(ValueError,match='Unexpected'):
        updates.stage_installer(result,tmp_path,FakeClient(FakeResponse()))


def test_public_installer_download_verified_sha_and_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(updates.sys,'platform','win32')
    data = b'MZ'+b'Z'*(updates.MIN_INSTALLER_BYTES + 700)
    sha=hashlib.sha256(data).hexdigest()
    meta={'name':'STAR-Setup-v0.8.3.exe','digest':'sha256:'+sha,'size':len(data),'browser_download_url':'https://github.com/oncoursemail/Star-Intelligence-Downloads/releases/download/v0.8.3/STAR-Setup-v0.8.3.exe'}
    result=updates.UpdateResult(True,'0.8.3',updates.PUBLIC_RELEASES_URL,repository=updates.PUBLIC_REPO,assets=(meta,))
    fake=FakeClient(FakeResponse(data=data))
    staged=updates.stage_installer(result,tmp_path,fake)
    assert staged.path.read_bytes()==data
    assert staged.checksum_verified and staged.expected_sha256==sha
    assert len(fake.stream_calls)==1
    other=FakeClient(FakeResponse(status_code=500))
    assert updates.stage_installer(result,tmp_path,other)==staged
    assert len(other.stream_calls)==0


def test_public_download_tampered_payload_is_never_installed(tmp_path,monkeypatch):
    monkeypatch.setattr(updates.sys,'platform','win32')
    data=b'MZ'+b'Q'*(updates.MIN_INSTALLER_BYTES+2)
    meta={'name':'STAR-Setup-v0.8.3.exe','digest':'sha256:'+'a'*64,'size':len(data),'browser_download_url':'https://github.com/oncoursemail/Star-Intelligence-Downloads/releases/download/v0.8.3/STAR-Setup-v0.8.3.exe'}
    result=updates.UpdateResult(True,'0.8.3',updates.PUBLIC_RELEASES_URL,repository=updates.PUBLIC_REPO,assets=(meta,))
    with pytest.raises(ValueError,match='SHA-256'):
        updates.stage_installer(result,tmp_path,FakeClient(FakeResponse(data=data)))
    assert not list(tmp_path.rglob('*.part'))
    assert not list(tmp_path.rglob('*.exe'))


def test_launcher_uses_user_selected_exe_without_shell(tmp_path,monkeypatch):
    file=_fake_exe(tmp_path/'STAR-Setup-v0.8.3.exe')
    candidate=updates.select_downloaded_installer(file)
    monkeypatch.setattr(updates.sys,'platform','win32')
    recorded={}
    def fake_popen(args,**kwargs):
        recorded['args']=args
        recorded['kwargs']=kwargs
    monkeypatch.setattr(updates.subprocess,'Popen',fake_popen)
    updates.launch_installer(candidate)
    assert recorded['args']==[str(file)]
    assert recorded['kwargs']['shell'] is False
    assert recorded['kwargs']['cwd']==str(tmp_path)


def test_legacy_updater_with_powershell_folder_swap_is_not_used():
    assert not hasattr(updates,'schedule_upgrade')
    assert not hasattr(updates,'UPGRADE_SCRIPT')
    assert not hasattr(updates,'stage_update')
