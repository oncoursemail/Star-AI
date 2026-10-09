"""No GPU or Windows dependencies: verifies tool boundaries and desktop backend."""
import json
from pathlib import Path
import os
import subprocess
import sys
import pytest

from star.desktop_core import Settings, Conversations
from star.workspace import Workspace
from star.comfy import load_workflow
from star.media_features import video_frames


def test_settings_round_trip(tmp_path):
    a=Settings(model='qwen3.5:4b',workspace=str(tmp_path),workspace_edit=True)
    path=tmp_path/'settings.json'
    a.save(path)
    b=Settings.load(path)
    assert b.model=='qwen3.5:4b' and b.workspace_edit


@pytest.mark.parametrize('endpoint', ['http://evil.example:80/v1','http://127.0.0.1:11434/api','https://localhost:1234/v1',
                                  'http://127.0.0.1:99999/v1','http://127.0.0.1:1234/v1?x=1'])
def test_settings_refuse_nonlocal_or_malformed_endpoint(endpoint):
    with pytest.raises(ValueError):
        Settings(endpoint=endpoint).validate()


def test_studio_edit_requires_selected_instance():
    with pytest.raises(ValueError):
        Settings(studio_edit=True).validate()


def test_conversation_is_project_isolated(tmp_path):
    d=Conversations(tmp_path/'chat.db')
    d.add('A','user','A secret project plan')
    d.add('B','assistant','B project notes')
    assert len(d.recent('A'))==1 and len(d.recent('B'))==1
    d.close()


def test_workspace_access_and_writes(tmp_path):
    p=Workspace(tmp_path)
    with pytest.raises(PermissionError):
        p.call('workspace_write',{'path':'one.txt','content':'testing'})
    result=p.call('workspace_write',{'path':'one.txt','content':'hello star'},allow_write=True)
    assert result['bytes_written']==10
    assert 'hello star' in p.call('workspace_read',{'path':'one.txt'})['content']
    assert len(p.call('workspace_search',{'query':'star'})['matches'])==1
    assert p.call('workspace_list',{'path':'.'})['items']


def test_workspace_blocks_escape_and_credentials(tmp_path):
    (tmp_path/'normal.txt').write_text('good')
    p=Workspace(tmp_path)
    for name in ['../private.txt','/etc/passwd','.env','.git/config','id_ed25519','key.pem']:
        with pytest.raises((PermissionError,ValueError,FileNotFoundError)):
            p.resolve(name,allow_missing=True)
    assert p.resolve('normal.txt').read_text()=='good'


def test_workspace_symlink_cannot_escape(tmp_path):
    external=tmp_path.parent/'external-secret.txt'
    external.write_text('secret')
    link=tmp_path/'link.txt'
    try:link.symlink_to(external)
    except OSError:pytest.skip('Symlinks not enabled')
    with pytest.raises(PermissionError):
        Workspace(tmp_path).call('workspace_read',{'path':'link.txt'})


def test_workspace_rejects_unexpected_parameters(tmp_path):
    with pytest.raises(Exception):
        Workspace(tmp_path).call('workspace_write',{'path':'one.txt','content':'x','command':'cmd'},allow_write=True)


def test_comfy_accepts_only_local_workflow_nodes(tmp_path):
    path=tmp_path/'work.json'
    path.write_text(json.dumps({'6':{'class_type':'CLIPTextEncode','inputs':{'text':'before'}}}))
    flow=load_workflow(path,prompt_text='new prompt',prompt_node='6')
    assert flow['6']['inputs']['text']=='new prompt'
    path.write_text(json.dumps({'6':{'class_type':'SomeCloudPaidNode','inputs':{'text':'before'}}}))
    with pytest.raises(PermissionError):
        load_workflow(path,prompt_text='new prompt',prompt_node='6')


def test_video_rejects_wrong_file_type(tmp_path):
    f=tmp_path/'notvideo.txt'
    f.write_text('nope')
    with pytest.raises(ValueError):
        video_frames(f,tmp_path/'frames')


def test_desktop_doctor_runs_without_gui(tmp_path):
    root=Path(__file__).resolve().parents[1]
    r=subprocess.run([sys.executable,str(root/'star_desktop.py'),'--doctor'],capture_output=True,text=True,cwd=root)
    assert r.returncode==0, r.stderr
    assert 'backend OK' in r.stdout


def test_workspace_denies_github_workflows(tmp_path):
    w=Workspace(tmp_path)
    with pytest.raises(PermissionError):
        w.call('workspace_write',{'path':'.github/workflows/build.yml','content':'evil'},allow_write=True)


def test_workspace_write_not_redirectable_by_predictable_symlink(tmp_path):
    outside=tmp_path.parent/'outside-staging.txt'
    outside.write_text('preserve')
    legacy=tmp_path/'sample.txt.star-tmp'
    try:legacy.symlink_to(outside)
    except OSError:pytest.skip('Symlinks not enabled')
    w=Workspace(tmp_path)
    w.call('workspace_write',{'path':'sample.txt','content':'new'},allow_write=True)
    assert outside.read_text()=='preserve'
    assert (tmp_path/'sample.txt').read_text()=='new'


def test_media_redaction_in_saved_transcripts():
    from star.desktop_core import redact_for_logs
    data={'messages':[{'type':'image_url','image_url':{'url':'data:image/png;base64,SECRET'}}]}
    safe=json.dumps(redact_for_logs(data))
    assert 'SECRET' not in safe
    assert 'stored separately' in safe
