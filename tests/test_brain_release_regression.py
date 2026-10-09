"""Regression tests for the 0% STAR Brain error and interrupted model downloads."""
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch
import zipfile
import pytest
from star import brain_setup as b


def digest(data):
    return hashlib.sha256(data).hexdigest()


def asset(tag='b11538', content=b'engine zip bytes'):
    name = f'llama-{tag}-bin-win-vulkan-x64.zip'
    return dict(name=name, size=len(content),
                digest='sha256:'+digest(content),
                browser_download_url=f'https://github.com/ggml-org/llama.cpp/releases/download/{tag}/{name}')


class Response:
    def __init__(self, *, data=None, blob=None, status=200, headers=None):
        self.data = data
        self.blob = blob
        self.status_code = status
        self.headers = headers if headers is not None else ({'content-length': str(len(blob))} if blob is not None else {})
        self.url = type('URL', (), {'scheme': 'https'})()
    def json(self):
        return self.data
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError('HTTP '+str(self.status_code))
    def __enter__(self): return self
    def __exit__(self,*args):return False
    def iter_bytes(self,n):
        for i in range(0,len(self.blob),n):yield self.blob[i:i+n]


class ReleaseClient:
    def __init__(self):
        self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append(url)
        if url==b.ENGINE_RELEASE:
            return Response(data={'tag_name':'v0.6.0','draft':False,'prerelease':False,'assets':[{'name':'nightly-tag.txt'}]})
        if url==b.ENGINE_BUILDS:
            return Response(data=[{'tag_name':'b11538','draft':False,'prerelease':True,'assets':[asset()]}])
        raise AssertionError('unexpected url: '+url)


def test_stable_pointer_only_release_falls_back_to_numbered_build():
    events=[]
    release, chosen=b._select_engine_release(ReleaseClient(),events.append)
    assert release['tag_name']=='b11538'
    assert chosen['name']=='llama-b11538-bin-win-vulkan-x64.zip'
    assert any('no Windows app' in e.get('phase','') for e in events)
    assert b._engine_asset(release)==chosen


def test_engine_rejects_unverified_or_nonofficial_candidates():
    chosen=asset()
    with pytest.raises(ValueError): b._engine_asset({'tag_name':'b11538','prerelease':True,'assets':[dict(chosen,digest='')]})
    with pytest.raises(ValueError): b._engine_asset({'tag_name':'b11538','prerelease':True,'assets':[dict(chosen,browser_download_url='https://example.com/evil.zip')]})
    with pytest.raises(ValueError): b._engine_asset({'tag_name':'v1alpha','prerelease':True,'assets':[chosen]})
    with pytest.raises(ValueError): b._engine_asset({'tag_name':'b0','prerelease':True,'assets':[chosen]})


def test_fallback_archive_digest_is_pinned_to_official_release():
    release, blob=b._fallback_engine_release()
    assert release['tag_name']=='b11429'
    assert blob['digest']=='sha256:'+b.ENGINE_FALLBACK_SHA
    assert blob['browser_download_url'].startswith('https://github.com/ggml-org/llama.cpp/')


def test_model_revision_and_projector_checksums_are_pinned():
    assert len(b.MODEL_REVISION)==40
    assert b.MODEL_SHAS[b.MODEL_FILES[0]]=='25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c'
    assert b.MODEL_SHAS[b.MODEL_FILES[1]]=='ae08d9d7eceb8f2d0672d61b5e6aa78b611f2942b55ed71d21414980cc454b91'
    assert b.MODEL_REVISION in b.MODEL_URL


def test_resumes_partial_verified_download(tmp_path):
    content=b'good new model bytes'*20
    path=tmp_path/'qwen.gguf'
    partial=content[:90]
    path.with_suffix('.gguf.part').write_bytes(partial)
    class Client:
        def stream(self,method,url,**kwargs):
            assert kwargs['headers']=={'Range':'bytes=90-'}
            return Response(blob=content[90:],status=206,
                            headers={'content-range':f'bytes 90-{len(content)-1}/{len(content)}',
                                     'content-length':str(len(content)-90)})
    events=[]
    b._download_verified(Client(),'https://huggingface.co/model',path,digest(content),10000,events.append,'model')
    assert path.read_bytes()==content
    assert events[-1]['finished']


def test_ignored_range_restarts_safely(tmp_path):
    content=b'whole payload'
    path=tmp_path/'model.gguf'
    path.with_suffix('.gguf.part').write_bytes(b'wrong and old')
    class Client:
        def stream(self,method,url,**kwargs):return Response(blob=content,status=200)
    b._download_verified(Client(),'https://huggingface.co/model',path,digest(content),10000,lambda x:None,'model')
    assert path.read_bytes()==content


def test_installer_from_fake_official_api_to_ready_state(tmp_path,monkeypatch):
    engine=io.BytesIO()
    with zipfile.ZipFile(engine,'w') as z:z.writestr('release/llama-server.exe',b'fake engine binary')
    zipped=engine.getvalue()
    inputs={'model.gguf':b'test model bytes','vision.gguf':b'test projector bytes'}
    e=asset(content=zipped)
    monkeypatch.setattr(b.sys,'platform','win32')
    monkeypatch.setattr(b,'MODEL_FILES',tuple(inputs))
    monkeypatch.setattr(b,'MODEL_SHAS',{k:digest(v) for k,v in inputs.items()})
    monkeypatch.setattr(b,'MODEL_SIZES',{k:len(v) for k,v in inputs.items()})
    monkeypatch.setattr(b,'MIN_FREE_BYTES',0)
    class Client:
        def get(self,url,**kw):
            if url==b.ENGINE_RELEASE:return Response(data={'tag_name':'v0.6.0','assets':[]})
            if url==b.ENGINE_BUILDS:return Response(data=[{'tag_name':'b11538','prerelease':True,'draft':False,'assets':[e]}])
            raise AssertionError(url)
        def stream(self, method,url,**kw):
            if url==e['browser_download_url']:return Response(blob=zipped)
            for k,v in inputs.items():
                if url.endswith('/'+k):return Response(blob=v)
            raise AssertionError(url)
    events=[]
    info=b.install_brain(tmp_path,progress=events.append,client=Client())
    assert Path(info.executable).is_file()
    assert Path(info.model).read_bytes()==inputs['model.gguf']
    assert Path(info.projector).read_bytes()==inputs['vision.gguf']
    assert b.BrainInstall.load(tmp_path/'brain.json')==info
    assert any(x.get('overall_total') for x in events)
    assert events[-1]['overall_total']==events[-1]['overall_downloaded']


def test_promotes_completed_part_without_request(tmp_path):
    complete = b'complete bytes of gguf file'
    path = tmp_path/'model.gguf'
    path.with_suffix('.gguf.part').write_bytes(complete)
    class NoNetwork:
        def stream(self,method,url,**kwargs):
            raise AssertionError('Already complete; do not re-download')
    b._download_verified(NoNetwork(),'https://huggingface.co/model',path,digest(complete),1000,lambda _:None,'model')
    assert path.read_bytes()==complete
    assert not path.with_suffix('.gguf.part').exists()


def test_rebranded_star_uses_measured_oled_gold_tokens():
    from star.version import __version__
    from star.design_system import COLORS, contrast_ratio, stylesheet
    root=Path(__file__).resolve().parents[1]
    style=stylesheet()
    assert 'QFrame#StarBubble' in style
    assert COLORS['gold'] in style and COLORS['black'] in style
    assert contrast_ratio(COLORS['text'],COLORS['canvas'])>=4.5
    assert __version__ == '0.6.0'
    assert (root/'assets/star.ico').is_file()
