"""Offline app routing and bounded connection evidence; no owner profile or Studio."""
import asyncio
import json
from dataclasses import asdict

import pytest

from star import desktop_core
from star.desktop_core import Settings, check_studio
from star.react_shell import apply_setting_changes, PERMITTED_SETTINGS
from star import studio_connections as connections, local_mcp


@pytest.fixture(autouse=True)
def isolated_desktop_home(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_core, 'app_data', lambda: tmp_path)


def evidence(target='local_pc', studios=None, **changes):
    return {'status':'tools_discovered_no_instances' if studios==[] else 'tools_and_instances_discovered','target':target,
            'server_name':'STAR local MCP','local_mcp':'memory','tool_count':30,
            'studios':[{'id':'local-1','name':'Test Place'}] if studios is None else studios,
            'selected':None,**changes}


def test_default_and_old_profiles_use_this_pc_even_with_an_operator_launcher(monkeypatch,tmp_path):
    monkeypatch.setenv('STAR_STUDIO_MCP_COMMAND',json.dumps(['operator-launcher','practice']))
    assert Settings().studio_target=='local_pc'
    settings=tmp_path/'settings.json'
    settings.write_text(json.dumps({'model':'test','studio_id':'old-id','studio_edit':True,'studio_luau':True}),encoding='utf-8')
    assert Settings.load(settings).studio_target=='local_pc'
    migrated=Settings.load(settings)
    assert migrated.studio_id=='' and not migrated.studio_edit and not migrated.studio_luau
    Settings(studio_target='host_launcher',studio_id='explicit',studio_edit=True,studio_luau=True).save(settings)
    explicit=Settings.load(settings)
    assert explicit.studio_target=='host_launcher' and explicit.studio_id=='explicit'
    assert explicit.studio_edit and explicit.studio_luau
    assert 'STAR_STUDIO_MCP_COMMAND' not in json.dumps(asdict(Settings()))


@pytest.mark.parametrize('target',['unknown','auto','ssh operator',None,False])
def test_settings_reject_arbitrary_routes(target):
    with pytest.raises(ValueError):Settings(studio_target=target).validate()


def test_route_changes_revoke_instance_and_permissions_even_if_resubmitted_in_same_save():
    current=Settings(studio_id='local-1',studio_edit=True,studio_luau=True)
    changed=apply_setting_changes(current,{'studio_target':'host_launcher','studio_id':'remote-1',
        'studio_edit':True,'studio_luau':True,'launcher':['untrusted'],'command':'anything'})
    assert changed.studio_target=='host_launcher'
    assert changed.studio_id=='' and not changed.studio_edit and not changed.studio_luau
    assert 'studio_id' not in PERMITTED_SETTINGS and 'launcher' not in PERMITTED_SETTINGS
    # The same explicit route is a normal save, not an implicit permission revocation.
    kept=apply_setting_changes(Settings(studio_id='same'),{'studio_target':'local_pc'})
    assert kept.studio_id=='same'


def test_saved_configuration_is_not_reported_connected_without_a_probe(monkeypatch):
    current=Settings(studio_id='old')
    report=connections.connection_status(current)
    assert report['state']=='not_checked' and not report['selected_valid'] and not report['instances']
    monkeypatch.delenv('STAR_STUDIO_MCP_COMMAND',raising=False)
    report=connections.connection_status(Settings(studio_target='host_launcher'))
    assert report['state']=='unconfigured' and report['local_mcp']=='not_checked'


def test_explicit_home_drives_app_status_discovery_and_selection_without_target_or_permission_import(monkeypatch, tmp_path):
    from dataclasses import asdict
    path=tmp_path/'practice'/'studio'/'remote.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'target':'pc','command':['fixture-launcher','private-argument']}))
    home=path.parent.parent
    monkeypatch.delenv(local_mcp.studio.COMMAND_ENV,raising=False)
    current=Settings(studio_target='host_launcher',studio_id='old',studio_edit=True,studio_luau=True)
    before=asdict(current)
    status=connections.connection_status(current,home=home)
    assert status['state']=='not_checked' and status['target']=='host_launcher' and not status['selected_valid']
    assert connections.connection_status(current,home=tmp_path/'other')['state']=='unconfigured'
    calls=[]
    async def discover(**kwargs):
        calls.append(kwargs)
        return evidence(target='host_launcher')
    monkeypatch.setattr(local_mcp,'discover',discover)
    report=check_studio(current,home)
    assert calls==[{'target':'host_launcher','home':home}]
    assert report['state']=='connected' and report['local_mcp']=='memory' and not report['selected_valid']
    assert asdict(current)==before
    selected=asyncio.run(connections.select_instance(current,'local-1',home=home))
    assert calls[-1]=={'target':'host_launcher','home':home} and selected['selected_valid']
    assert current.studio_id=='local-1' and not current.studio_edit and not current.studio_luau
    assert 'private-argument' not in json.dumps(report)


@pytest.mark.parametrize('raw',[None,'{}','[]','invalid fixture-secret','{"command":[]}',' '*22001])
def test_app_bad_profile_configuration_is_unconfigured_without_connector_attempt(monkeypatch,tmp_path,raw):
    monkeypatch.delenv(local_mcp.studio.COMMAND_ENV,raising=False)
    if raw is not None:
        path=tmp_path/'studio'/'remote.json'
        path.parent.mkdir()
        path.write_text(raw)
    async def discover(**kwargs):pytest.fail('Bad host configuration must not attempt discovery')
    monkeypatch.setattr(local_mcp,'discover',discover)
    current=Settings(studio_target='host_launcher',studio_id='old')
    report=check_studio(current,tmp_path)
    assert report['state']=='unconfigured' and not report['selected_valid']
    assert report['local_mcp']=='not_checked' and not report['instances']
    assert 'fixture-secret' not in json.dumps(report) and current.studio_id=='old'


def test_app_this_pc_ignores_bad_profile_command(monkeypatch,tmp_path):
    monkeypatch.setattr(local_mcp.studio,'configured_command',lambda *_:pytest.fail('This PC ignores operator host files'))
    async def discover(**kwargs):return evidence()
    monkeypatch.setattr(local_mcp,'discover',discover)
    assert connections.connection_status(Settings(),home=tmp_path)['state']=='not_checked'
    assert check_studio(Settings(),tmp_path)['state']=='connected'


def test_react_snapshot_uses_settings_home_for_command_but_app_home_for_chats(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from star import react_shell
    persistence, configuration=tmp_path/'persistence',tmp_path/'configuration'
    persistence.mkdir()
    path=configuration/'studio'/'remote.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'command':['fixture-launcher']}))
    settings_file=configuration/'settings.json'
    Settings(studio_target='host_launcher').save(settings_file)
    monkeypatch.delenv(local_mcp.studio.COMMAND_ENV,raising=False)
    monkeypatch.setattr(react_shell,'app_data',lambda:persistence)
    status=SimpleNamespace(status=lambda:{},close=lambda:None)
    monkeypatch.setattr(react_shell,'ToolWorkshop',lambda **_:status)
    monkeypatch.setattr(react_shell,'for_settings',lambda *_:status)
    monkeypatch.setattr(react_shell,'MCPGateway',lambda *_:status)
    for name in ('get_dashboard','learning_status','roblox_state','credential_status','server_status','read_build_info'):
        monkeypatch.setattr(react_shell,name,lambda *_:{})
    runtime=SimpleNamespace(status=lambda:'stopped',router_running=lambda:False)
    snapshot=react_shell._get_state(settings_file,runtime)
    assert snapshot['studio']['state']=='not_checked' and snapshot['studio']['target']=='host_launcher'
    assert (persistence/'conversations.sqlite3').is_file()
    assert not (configuration/'conversations.sqlite3').exists()


def test_app_discovery_uses_actual_local_mcp_contract_and_explicit_target(monkeypatch):
    calls=[]
    async def discover(**kwargs):
        calls.append(kwargs)
        return evidence(target=kwargs['target'])
    monkeypatch.setattr(local_mcp,'discover',discover)
    report=check_studio(Settings(studio_id='local-1'))
    assert calls==[{'target':'local_pc','home':desktop_core.app_data()}]
    assert report['state']=='connected' and report['selected_valid']
    assert report['local_mcp']=='memory' and report['tool_count']==30
    assert report['instances']==[{'id':'local-1','name':'Test Place'}]
    assert report['checked_at']


def test_no_instance_is_not_connected_and_no_first_instance_is_auto_selected(monkeypatch):
    async def empty(**kwargs):return evidence(studios=[])
    monkeypatch.setattr(local_mcp,'discover',empty)
    report=check_studio(Settings())
    assert report['state']=='no_instances' and not report['selected_valid']
    report=connections.normalize_probe(Settings(),evidence())
    assert report['selected_id']=='' and not report['selected_valid']


@pytest.mark.parametrize('bad',[
    {'target':'host_launcher'},{'local_mcp':'not_checked'},{'server_name':'foreign'},
    {'tool_count':True},{'tool_count':1001},{'status':'configured'},
    {'status':'tools_discovered_no_instances'},
    {'status':'tools_and_instances_discovered','studios':[]},
    {'studios':[{'id':'x','name':'place'}]*2},{'studios':[{'id':'x','name':'place'}]*33},
    {'studios':[{'id':'x\nsecret','name':'place'}]},{'studios':[{'id':'x','name':'y'*201}]},
])
def test_malformed_or_wrong_route_discovery_never_becomes_connected(monkeypatch,bad):
    async def malformed(**kwargs):return evidence(**bad)
    monkeypatch.setattr(local_mcp,'discover',malformed)
    report=check_studio(Settings(studio_id='x'))
    assert report['state']=='unavailable' and not report['instances'] and not report['selected_valid']


def test_probe_failure_is_generic_and_stale_success_is_invalidated(monkeypatch):
    async def fail(**kwargs):raise RuntimeError('private endpoint/key/raw data must not escape')
    monkeypatch.setattr(local_mcp,'discover',fail)
    report=check_studio(Settings(studio_id='local-1'))
    assert report['state']=='unavailable' and report['reason_code']=='connection_failed'
    assert 'private endpoint' not in json.dumps(report) and report['instances']==[]
    old=connections.normalize_probe(Settings(studio_id='local-1'),evidence())
    assert connections.connection_status(Settings(studio_id='another'),old)['state']=='not_checked'
    assert connections.connection_status(Settings(studio_target='host_launcher'),old)['state']!='connected'


def test_probe_deadline_cancels_and_has_no_fallback_or_replay(monkeypatch):
    calls=[]
    async def wait(**kwargs):
        calls.append(kwargs)
        await asyncio.Event().wait()
    monkeypatch.setattr(local_mcp,'discover',wait)
    monkeypatch.setattr(connections,'PROBE_SECONDS',0.01)
    report=check_studio(Settings())
    assert report['state']=='unavailable' and report['reason_code']=='timeout'
    assert calls==[{'target':'local_pc','home':desktop_core.app_data()}]


def test_desktop_probe_budget_covers_each_bounded_stage_and_local_status():
    from star import studio
    assert connections.PROBE_SECONDS == (studio.INITIALIZE_SECONDS + studio.DISCOVERY_SECONDS
                                          + studio.INSTANCE_SECONDS + 5)
    assert 15 < connections.PROBE_SECONDS <= 70


def test_app_reports_no_instances_after_a_real_bounded_empty_attach_window(monkeypatch):
    from contextlib import asynccontextmanager
    from star import studio
    from tests.studio_fake import FakeStudio, text
    fake=FakeStudio()
    routes=[]
    attempts=[]
    async def empty(name,arguments=None):
        assert name=='list_roblox_studios' and arguments=={}
        attempts.append(name)
        return text({'studios':[]})
    @asynccontextmanager
    async def connect(*,target):
        routes.append(target)
        await asyncio.sleep(.01)
        yield fake
    fake.call_tool=empty
    monkeypatch.setattr(studio,'connect',connect)
    monkeypatch.setattr(studio,'INSTANCE_SECONDS',.1)
    monkeypatch.setattr(studio,'INSTANCE_POLL_SECONDS',.005)
    report=check_studio(Settings())
    assert routes==['local_pc'] and len(attempts)>=2
    assert report['state']=='no_instances' and report['tool_count']==30
    assert report['local_mcp']=='memory' and report['selected_valid'] is False
    assert report['instances']==[] and not fake.history and not fake.scripts


def test_selection_requires_fresh_same_route_discovery_and_resets_permissions(monkeypatch):
    calls=[]
    async def discover(**kwargs):calls.append(kwargs);return evidence()
    monkeypatch.setattr(local_mcp,'discover',discover)
    settings=Settings(studio_id='old',studio_edit=True,studio_luau=True)
    with pytest.raises(ValueError):asyncio.run(connections.select_instance(settings,'absent'))
    assert settings.studio_id=='old' and settings.studio_edit
    report=asyncio.run(connections.select_instance(settings,'local-1'))
    assert report['selected_valid'] and settings.studio_id=='local-1'
    assert not settings.studio_edit and not settings.studio_luau and len(calls)==2


def test_cancellation_remains_cancellation(monkeypatch):
    async def cancel(**kwargs):raise asyncio.CancelledError
    monkeypatch.setattr(local_mcp,'discover',cancel)
    with pytest.raises(asyncio.CancelledError):check_studio(Settings())


@pytest.mark.parametrize('target', ['local_pc', 'host_launcher'])
@pytest.mark.parametrize('separate_configuration', [False, True])
def test_chat_tool_turn_uses_the_host_selected_local_mcp_proxy(monkeypatch, tmp_path, target, separate_configuration):
    """Exercise the real run_task handoff; every provider and Studio endpoint is fake."""
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from star import desktop_core, doc_grounding

    calls=[]
    proxy=SimpleNamespace(discovered=[{'name':'get_studio_state','inputSchema':{'type':'object'}}],
        verdict=SimpleNamespace(editable=False,reason='Verified read-only synthetic place'),
        journal=SimpleNamespace(text=lambda:''))

    @asynccontextmanager
    async def connect(settings,home,*,studio_configuration_home=None):
        calls.append(('connect',settings.studio_target,settings.studio_id,home,studio_configuration_home))
        yield proxy
        calls.append(('closed',))

    @asynccontextmanager
    async def client(settings):
        yield SimpleNamespace()

    async def prepare(*args,**kwargs):return doc_grounding.Grounding()
    async def execute(**kwargs):
        calls.append(('execute',kwargs['studio'],kwargs['discovered'],kwargs['studio_id'],
                      kwargs['may_edit'],kwargs['allow_luau']))
        return 'Synthetic read-only answer',[],[]

    monkeypatch.setattr(desktop_core,'app_data',lambda:tmp_path)
    monkeypatch.setattr(desktop_core,'open_client',client)
    monkeypatch.setattr(desktop_core,'execute',execute)
    monkeypatch.setattr(doc_grounding,'prepare_async',prepare)
    monkeypatch.setattr(local_mcp,'connect_studio',connect)
    current=Settings(model='offline-test',studio_target=target,studio_id='selected',
        skills_enabled=False,graphify_enabled=False,roblox_research_enabled=False,
        tool_workshop_enabled=False,specialists_enabled=False)
    configuration=tmp_path/'operator-configuration' if separate_configuration else None
    assert desktop_core.run_task(current,'Read the open Roblox Studio place',mode='agent',
        studio_configuration_home=configuration)=='Synthetic read-only answer'
    assert calls==[('connect',target,'selected',tmp_path,configuration),
        ('execute',proxy,proxy.discovered,'selected',False,False),('closed',)]
    assert len(list((tmp_path/'runs').glob('*/answer.md')))==1
    if configuration is not None:
        assert not configuration.exists()
