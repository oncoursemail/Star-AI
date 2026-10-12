"""Hand-authored XML only: no Roblox, Luau, network, GPU, or keyring."""
from pathlib import Path
from unittest.mock import Mock

import pytest

from star import rbx_xml
from star.rbx_xml import RbxXMLError, read, summarize_script

FIXTURES = Path(__file__).parent / 'fixtures' / 'rbx_xml'


def xml_file(tmp_path, text, name='fixture.rbxmx', encoding='utf-8'):
    path = tmp_path / name
    path.write_text(text, encoding=encoding)
    return path


def test_model_tree_property_whitelist_and_inline_sources():
    model = read(FIXTURES / 'model.rbxmx')
    assert len(model.instances) == 6
    assert model.roots[0].name == 'Demo'
    assert model.roots[0].descendants == 5
    assert model.roots[0].script_count == 3
    pad = model.find('/Demo/Pad')
    assert pad.class_name == 'Part'
    assert pad.properties == {'Anchored': True, 'Transparency': .25,
                              'Size': {'type': 'Vector3', 'X': 4., 'Y': 1., 'Z': 4.}}
    assert model.roots[0].properties == {'PrimaryPart': 'RBX1'}
    script = model.find('/Demo/Logic/Server')
    assert script.properties == {'Disabled': False, 'RunContext': 1}
    assert script.source.startswith('local storage = game:GetService("ReplicatedStorage")\n')
    assert 'value < limit & valid' in model.find('/Demo/Logic/Settings').source
    assert 'remote:FireServer("ready")' in model.find('/Demo/Logic/Client').source
    assert not model.warnings


def test_place_has_multiple_roots_and_no_scripts():
    model = read(FIXTURES / 'place.rbxlx')
    assert len(model.instances) == 4
    assert [item.class_name for item in model.roots] == ['Workspace', 'ReplicatedStorage']
    assert model.find('/ReplicatedStorage/Submit').class_name == 'RemoteEvent'
    assert model.script_list() == []
    assert '4 instances; 0 scripts' in model.outline()


def test_script_index_is_deterministic_and_has_no_bodies():
    model = read(FIXTURES / 'model.rbxmx')
    scripts = model.script_list()
    assert [(s['kind'], s['line_count']) for s in scripts] == [('Script', 8), ('ModuleScript', 5), ('LocalScript', 2)]
    assert scripts[0]['summary'] == ('services: ReplicatedStorage; requires: script.Parent.Settings; '
                                     'remotes: remote.OnServerEvent, remote:FireClient; functions: onRequest')
    assert scripts[1]['summary'].endswith('functions: Settings.read')
    assert scripts[2]['summary'].endswith('remotes: remote:FireServer; functions: none detected')
    assert all('source' not in item for item in scripts)
    assert scripts == read(FIXTURES / 'model.rbxmx').script_list()


def test_outline_counts_depth_node_and_character_limits():
    model = read(FIXTURES / 'model.rbxmx')
    outline = model.outline(max_depth=1)
    assert outline.startswith('Roblox XML outline: 6 instances; 3 scripts.')
    assert '  Logic [Folder] (3 children; 3 descendants; 3 scripts)' in outline
    assert 'Server [Script]' not in outline
    assert '[3 instances omitted' in outline
    assert '[5 instances omitted' in model.outline(max_nodes=1)
    for budget in (0, 1, 40, 180, 1000):
        assert len(model.outline(budget_chars=budget)) <= budget
        assert len(model.focus('/Demo', budget_chars=budget)) <= budget
    assert model.outline() == model.outline()


def test_focus_is_exact_and_does_not_leak_siblings():
    model = read(FIXTURES / 'model.rbxmx')
    focused = model.focus('/Demo/Logic/Settings')
    assert model.find('/Demo/Logic/Settings').source in focused
    assert 'remote:FireClient' not in focused
    assert '/Demo/Logic/Client' not in focused
    subtree = model.focus('/Demo/Logic', budget_chars=10000)
    assert '/Demo/Logic/Server' in subtree and '/Demo/Logic/Client' in subtree
    assert 'Pad [Part]' not in subtree
    assert 'Source:' not in model.focus('/Demo/Pad')
    with pytest.raises(RbxXMLError, match='path not found'):
        model.focus('/Demo/Log')


def test_duplicate_empty_and_separator_names_are_unambiguous(tmp_path):
    path = xml_file(tmp_path, '''<roblox><Item class="Folder"><Properties><string name="Name">A/B</string></Properties>
      <Item class="Part"><Properties><string name="Name">Twin</string></Properties></Item>
      <Item class="Part"><Properties><string name="Name">Twin</string></Properties></Item>
      <Item class="Part"><Properties><string name="Name">Twin[1]</string></Properties></Item>
      <Item class="Part"><Properties><string name="Name"></string></Properties></Item>
      <Item class="Part"><Properties><string name="Name">%00</string></Properties></Item>
    </Item></roblox>''')
    model = read(path)
    assert len(model.instances) == 6
    assert model.find('/A%2FB/Twin[1]') is not model.find('/A%2FB/Twin[2]')
    assert model.find('/A%2FB/Twin%5B1%5D').name == 'Twin[1]'
    assert model.find('/A%2FB/%00').name == ''
    assert model.find('/A%2FB/%2500').name == '%00'
    with pytest.raises(RbxXMLError):
        model.find('/A%2FB/Twin')
    assert read(path).outline() == model.outline()


def test_lexer_ignores_comments_long_strings_and_templates():
    source = '''-- game:GetService("Fake")
--[==[ function counterfeit() remote:FireServer() ]==]
local a = "function fake() remote.OnServerEvent"
local b = [=[game:GetService("AlsoFake")]=]
local c = `remote:FireServer({value})`
local svc = game:GetService('Players')
local svc2 = game:GetService("Players")
local cfg = require(script.Parent.Config)
function Controller:start() end
Controller.stop = function() end
bus.Remote:InvokeServer()
bus.Remote.OnClientEvent:Connect(Controller.stop)
'''
    summary = summarize_script(source)
    assert summary == ('services: Players; requires: script.Parent.Config; '
                       'remotes: bus.Remote.OnClientEvent, bus.Remote:InvokeServer; '
                       'functions: Controller.stop, Controller:start')
    assert summarize_script(source) == summary


def test_empty_and_unavailable_sources_are_distinct(tmp_path):
    model = read(xml_file(tmp_path, '''<roblox>
      <Item class="Script"><Properties><ProtectedString name="Source"/></Properties></Item>
      <Item class="ModuleScript"><Properties><SharedString name="Source">reference</SharedString></Properties></Item>
    </roblox>'''))
    first, second = model.script_list()
    assert first['line_count'] == 0 and first['source_available']
    assert second['line_count'] == 0 and not second['source_available']
    assert 'unavailable' in second['summary']
    assert model.warnings == ['Source unavailable for /ModuleScript']


@pytest.mark.parametrize('encoding', ['utf-8', 'utf-8-sig', 'utf-16'])
def test_xml_unicode_and_bom(tmp_path, encoding):
    model = read(xml_file(tmp_path, '<roblox><Item class="Folder"><Properties><string name="Name">caf\u00e9</string></Properties></Item></roblox>', encoding=encoding))
    assert model.roots[0].name == 'caf\u00e9'
    assert model.find('/caf%C3%A9') is model.roots[0]


@pytest.mark.parametrize('suffix', ['.rbxm', '.rbxl', '.RBXM', '.RBXL'])
def test_binary_extensions_are_refused_before_reading(tmp_path, suffix):
    with pytest.raises(RbxXMLError, match='Binary Roblox.*export as XML'):
        read(tmp_path / ('missing' + suffix))


def test_disguised_binary_is_refused(tmp_path):
    path = tmp_path / 'binary.rbxmx'
    path.write_bytes(b'<roblox!\x89\xff\r\n\x1a\n\x00\x00')
    with pytest.raises(RbxXMLError, match='Binary Roblox'):
        read(path)


@pytest.mark.parametrize('encoding', ['utf-8', 'utf-16'])
def test_billion_laughs_is_refused_before_expansion(tmp_path, encoding):
    text = (FIXTURES / 'billion_laughs.rbxmx').read_text()
    if encoding == 'utf-16':
        text = text.replace('<?xml version="1.0"?>', '<?xml version="1.0" encoding="UTF-16"?>')
    with pytest.raises(RbxXMLError, match='DTDs, entities'):
        read(xml_file(tmp_path, text, encoding=encoding))


@pytest.mark.parametrize('declaration', [
    '<!DOCTYPE roblox SYSTEM "https://example.invalid/external.dtd">',
    '<!DOCTYPE roblox [<!ENTITY external SYSTEM "https://example.invalid/entity">]>',
    '<!DOCTYPE roblox [<!ENTITY % external SYSTEM "https://example.invalid/parameter">%external;]>',
    '<!DOCTYPE roblox []>',
])
def test_dtd_external_and_parameter_entities_are_refused(tmp_path, declaration):
    with pytest.raises(RbxXMLError, match='Unsafe Roblox XML'):
        read(xml_file(tmp_path, declaration + '<roblox/>'))


def test_oversized_file_is_refused_before_parser_feed(tmp_path, monkeypatch):
    path = tmp_path / 'oversized.rbxlx'
    with path.open('wb') as stream:
        stream.seek(rbx_xml.MAX_FILE_BYTES)
        stream.write(b'x')
    feed = Mock(side_effect=AssertionError('oversized content must not be parsed'))
    monkeypatch.setattr(rbx_xml.DefusedXMLParser, 'feed', feed)
    with pytest.raises(RbxXMLError, match='file-size'):
        read(path)
    feed.assert_not_called()


@pytest.mark.parametrize('limit,text,match', [
    ('MAX_XML_DEPTH', '<roblox>' + '<Item class="Folder">' * 8 + '</Item>' * 8 + '</roblox>', 'depth'),
    ('MAX_ELEMENTS', '<roblox>' + '<Meta/>' * 8 + '</roblox>', 'element-count'),
    ('MAX_INSTANCES', '<roblox>' + '<Item class="Part"/>' * 8 + '</roblox>', 'instance-count'),
    ('MAX_TEXT_CHARS', '<roblox><Meta>longer than allowed</Meta></roblox>', 'text-character'),
])
def test_structural_limits_run_during_parsing(tmp_path, monkeypatch, limit, text, match):
    monkeypatch.setattr(rbx_xml, limit, 4)
    with pytest.raises(RbxXMLError, match=match):
        read(xml_file(tmp_path, text))


@pytest.mark.parametrize('text', [
    '', '<roblox>', '<other/>', '<roblox version="3"/>', '<roblox><Item/></roblox>',
    '<roblox><Item class="Bad Class"/></roblox>',
    '<roblox><Meta><Item class="Part"/></Meta></roblox>',
    '<roblox><Item class="Part"><Properties/><Properties/></Item></roblox>',
    '<roblox><Item class="Part"><Properties><string name="Name">a</string><string name="Name">b</string></Properties></Item></roblox>',
    '<roblox><Item class="Part"><Properties><bool name="Anchored">maybe</bool></Properties></Item></roblox>',
    '<roblox><Item class="Part"><Properties><float name="Transparency">NaN</float></Properties></Item></roblox>',
    '<roblox><Item class="Part"><Properties><Vector3 name="Size"><X>1</X></Vector3></Properties></Item></roblox>',
])
def test_malformed_and_invalid_properties_are_refused(tmp_path, text):
    with pytest.raises(RbxXMLError):
        read(xml_file(tmp_path, text))


def test_empty_roblox_and_artifact_suffix_override(tmp_path):
    path = xml_file(tmp_path, '<roblox/>', name='digest')
    with pytest.raises(RbxXMLError, match='Choose'):
        read(path)
    model = read(path, suffix='.rbxlx')
    assert model.instances == {} and '0 instances' in model.outline()


def test_cancellation_is_not_rewritten_as_malformed(tmp_path):
    class Stopped(RuntimeError):
        pass
    count = 0
    def check():
        nonlocal count
        count += 1
        if count == 5:
            raise Stopped('cancelled')
    with pytest.raises(Stopped):
        read(FIXTURES / 'model.rbxmx', check=check)
    assert count == 5


@pytest.mark.parametrize('value', [-1, 2.5, True])
def test_invalid_output_limits(value):
    model = read(FIXTURES / 'model.rbxmx')
    with pytest.raises(RbxXMLError):
        model.outline(max_depth=value)
    with pytest.raises(RbxXMLError):
        model.focus('/Demo', budget_chars=value)
