"""Regressions for no-login Releases and in-place app upgrade safety.

These tests do not run an installer or contact GitHub. The native Windows job
builds the actual STAR Setup file and runs the packaged diagnostic.
"""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import pytest

from star import updates
from star.version import REPO, PUBLIC_REPO, __version__


class Response:
    def __init__(self, code=200, body=None, data=b''):
        self.status_code=code
        self.body=body or {}
        self.data=data
        self.url=SimpleNamespace(scheme='https')
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')
    def json(self):return self.body
    def __enter__(self):return self
    def __exit__(self, *args):return False
    def iter_bytes(self, size):
        for i in range(0,len(self.data),size):yield self.data[i:i+size]


class Client:
    def __init__(self, responses):
        self.responses=responses
        self.called=[]
    def get(self, url, **kwargs):
        self.called.append(url)
        return self.responses[url]
    def stream(self, method, url, **kwargs):
        self.called.append(url)
        return self.responses[url]


def sample_release(repo, data, version='0.8.2'):
    name=f'STAR-Setup-v{version}.exe'
    return {'tag_name':'v'+version, 'html_url':f'https://github.com/{repo}/releases/tag/v{version}',
            'assets':[{'name':name,'size':len(data),'digest':'sha256:'+hashlib.sha256(data).hexdigest(),
                'browser_download_url':f'https://github.com/{repo}/releases/download/v{version}/{name}'}]}


def test_source_release_public_without_github_cli():
    payload=b'MZ'+b'X'*(updates.MIN_INSTALLER_BYTES + 400)
    response={updates.PUBLIC_API:Response(404),updates.API:Response(200,sample_release(REPO,payload))}
    result=updates.get_latest(Client(response))
    assert result.available and not result.requires_browser
    assert result.anonymous_access and result.repository==REPO
    assert result.version=='0.8.2'
    assert updates._trusted_setup_asset(result)['name']=='STAR-Setup-v0.8.2.exe'


def test_private_source_returns_manual_browser_fallback():
    result=updates.get_latest(Client({updates.PUBLIC_API:Response(404),updates.API:Response(404)}))
    assert result.requires_browser and not result.available
    assert not result.anonymous_access


def test_forged_private_result_cannot_start_auto_download():
    data=b'MZ'+b'X'*(updates.MIN_INSTALLER_BYTES + 400)
    result=updates.UpdateResult(True,'0.8.2',updates.RELEASES_URL,
         repository=REPO,assets=tuple(sample_release(REPO,data)['assets']))
    with pytest.raises(PermissionError):updates._trusted_setup_asset(result)


def test_source_public_installer_download_is_hash_verified(tmp_path, monkeypatch):
    monkeypatch.setattr(updates.sys,'platform','win32')
    data=b'MZ'+b'Y'*(updates.MIN_INSTALLER_BYTES + 400)
    meta=sample_release(REPO,data)
    c=Client({updates.PUBLIC_API:Response(404),updates.API:Response(200,meta),
              meta['assets'][0]['browser_download_url']:Response(200,data=data)})
    detected=updates.get_latest(c)
    saved=updates.stage_installer(detected,tmp_path,c)
    assert saved.path.read_bytes()==data
    assert saved.checksum_verified and saved.expected_sha256
    assert saved.path.parent.name=='v0.8.2'


def test_verified_auto_launch_restarts_via_silent_installer(tmp_path, monkeypatch):
    monkeypatch.setattr(updates.sys,'platform','win32')
    installer=tmp_path/'STAR-Setup-v0.8.2.exe'
    installer.write_bytes(b'MZ'+b'Z'*(updates.MIN_INSTALLER_BYTES+400))
    digest=hashlib.sha256(installer.read_bytes()).hexdigest()
    candidate=updates.InstallerCandidate(installer,'0.8.2',True,digest)
    events=[]
    monkeypatch.setattr(updates.subprocess,'Popen',lambda argv, **kwargs:events.append((argv,kwargs)))
    updates.launch_installer(candidate,unattended=True)
    args,kwargs=events[0]
    assert args[0]==str(installer)
    assert '/SILENT' in args and '/CLOSEAPPLICATIONS' in args and '/NORESTART' in args
    assert kwargs['shell'] is False
    with pytest.raises(PermissionError):
        updates.launch_installer(updates.InstallerCandidate(installer,'0.8.2',False),unattended=True)


def test_old_update_cleanup_only_removes_outdated_versioned_downloads(tmp_path):
    saved=tmp_path/'conversations.sqlite3';saved.write_text('chat history')
    models=tmp_path/'models';models.mkdir();(models/'brain.gguf').write_text('weights')
    updates_dir=tmp_path/'updates';updates_dir.mkdir()
    for name in ('v0.5.1','v0.6.0','v0.6.1','unrelated'):
        folder=updates_dir/name;folder.mkdir();(folder/'Setup.exe').write_text('data')
    removed=updates.prune_obsolete_update_packages(tmp_path,current_version='0.6.1')
    assert set(removed)=={'v0.5.1','v0.6.0'}
    assert (updates_dir/'v0.6.1'/'Setup.exe').exists()
    assert (updates_dir/'unrelated'/'Setup.exe').exists()
    assert saved.read_text()=='chat history'
    assert (models/'brain.gguf').read_text()=='weights'


def test_windows_installer_replaces_old_dependencies_and_restarts_silently():
    script=(Path(__file__).resolve().parents[1]/'installer/STAR.iss').read_text()
    assert 'AppId={{E2B5518B-30A1-409D-AF44-6F773BF05C97}' in script
    assert '[InstallDelete]' in script
    assert 'Type: filesandordirs; Name: "{app}\\_internal"' in script
    assert 'Flags: nowait skipifnotsilent' in script
    assert 'Flags: nowait postinstall skipifsilent' in script
    guarded=script.split('[InstallDelete]',1)[1].split('[Files]',1)[0]
    assert '{userappdata}\\STAR' not in guarded.splitlines()[1:]


def test_site_downloads_match_an_existing_release_channel():
    from star.version import REPO
    import json
    root=Path(__file__).resolve().parents[1]
    link=json.loads((root/'site/version.json').read_text())['download']
    assert link == f'https://github.com/{REPO}/releases/latest'


def test_newer_source_release_beats_older_public_mirror():
    """A lagging download mirror must not mask a newer verified public release."""
    payload=b'MZ'+b'Q'*(updates.MIN_INSTALLER_BYTES+400)
    responses={
        updates.PUBLIC_API:Response(200,sample_release(PUBLIC_REPO,payload,'0.8.0')),
        updates.API:Response(200,sample_release(REPO,payload,'0.9.0')),
    }
    result=updates.get_latest(Client(responses))
    assert result.available
    assert result.version=='0.9.0'
    assert result.repository==REPO


def test_checked_download_progress_and_local_cache(tmp_path,monkeypatch):
    """Progress uses actual bytes and never deletes the user's model or chats."""
    monkeypatch.setattr(updates.sys,'platform','win32')
    user_data=tmp_path/'conversations.sqlite3';user_data.write_text('existing chat')
    model=tmp_path/'models'/'installed.gguf';model.parent.mkdir();model.write_text('weights')
    payload=b'MZ'+b'P'*(updates.MIN_INSTALLER_BYTES+400)
    release=sample_release(REPO,payload)
    uri=release['assets'][0]['browser_download_url']
    client=Client({uri:Response(200,data=payload)})
    result=updates.UpdateResult(True,'0.8.2',release['html_url'],
       repository=REPO,anonymous_access=True,assets=tuple(release['assets']))
    events=[]
    one=updates.stage_installer(result,tmp_path,client,progress=lambda done,total:events.append((done,total)))
    assert events[-1]==(len(payload),len(payload))
    assert all(0<=done<=total for done,total in events)
    assert one.checksum_verified
    events.clear()
    two=updates.stage_installer(result,tmp_path,client,progress=lambda done,total:events.append((done,total)))
    assert two.path==one.path
    assert events==[(len(payload),len(payload))]
    assert client.called.count(uri)==1  # Cached file was hash-checked, not redownloaded.
    assert user_data.read_text()=='existing chat'
    assert model.read_text()=='weights'
