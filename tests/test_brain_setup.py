"""No network or executable downloads in unit tests."""
import hashlib
import io
import json
import zipfile
from pathlib import Path
import pytest
from star import brain_setup as b


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def test_selected_upstream_sources_are_explicit():
    assert b.MODEL_REPO == 'lmstudio-community/Qwen3.5-4B-GGUF'
    assert all(v.endswith('.gguf') for v in b.MODEL_FILES)


def test_model_sha_source_metadata():
    tree=[{'path':name,'lfs':{'oid':_sha(name.encode())}} for name in b.MODEL_FILES]
    assert b._model_shas(tree)=={name:_sha(name.encode()) for name in b.MODEL_FILES}
    with pytest.raises(ValueError):b._model_shas(tree[:1])
    with pytest.raises(ValueError):b._model_shas([{'path':b.MODEL_FILES[0],'lfs':{}}])


def test_engine_asset_is_checked():
    sha='a'*64
    asset={'name':'llama-b11000-bin-win-vulkan-x64.zip','digest':'sha256:'+sha,
           'browser_download_url':'https://github.com/ggml-org/llama.cpp/releases/download/b11000/llama-b11000-bin-win-vulkan-x64.zip'}
    assert b._engine_asset({'assets':[asset], 'draft':False,'prerelease':False})==asset
    with pytest.raises(ValueError):b._engine_asset({'assets':[dict(asset,digest='')], 'draft':False})
    with pytest.raises(ValueError):b._engine_asset({'assets':[asset], 'prerelease':True})


def test_verified_download_accepts_only_correct_hash(tmp_path):
    class FakeStream:
        def __init__(self,data):
            self.url=type('URL',(),{'scheme':'https'})()
            self.headers={'content-length':str(len(data))}
            self.data=data
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def raise_for_status(self):pass
        def iter_bytes(self,n):yield self.data
    class FakeClient:
        def stream(self, method,url,**kwargs):return FakeStream(b'correct payload')
    path=tmp_path/'file.zip'
    events=[]
    b._download_verified(FakeClient(),'https://github.com/test/test',path,_sha(b'correct payload'),1000,events.append,'download')
    assert path.read_bytes()==b'correct payload' and events
    with pytest.raises(ValueError):
        b._download_verified(FakeClient(),'https://github.com/test/test',path,_sha(b'wrong'),1000,events.append,'download')
    assert not (tmp_path/'file.zip.part').exists()


def test_extract_rejects_path_escape_and_requires_engine(tmp_path):
    z=tmp_path/'evil.zip'
    with zipfile.ZipFile(z,'w') as w:w.writestr('../escape.exe',b'bad')
    with pytest.raises(ValueError):b._safe_extract(z,tmp_path/'extract')
    assert not (tmp_path/'escape.exe').exists()
    with zipfile.ZipFile(z,'w') as w:w.writestr('llama-server.exe',b'fake-engine')
    assert b._safe_extract(z,tmp_path/'ok').name=='llama-server.exe'


def test_saved_brain_missing_engine_returns_none(tmp_path):
    path=tmp_path/'brain.json'
    path.write_text(json.dumps({'executable':str(tmp_path/'missing.exe'),'model':'x','projector':'y','engine_version':'b100'}))
    assert b.BrainInstall.load(path) is None
