"""Execute the actual Qt bridge chat methods without importing Qt or running a GPU."""
import ast
import inspect
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from star import react_shell as shell
from star.desktop_core import Settings, Conversations


def bridge_class():
    tree = ast.parse(inspect.getsource(shell.launch))
    bridge = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == 'Bridge')
    names = {'_run_chat', '_run_image', '_image_setup_reply'}
    methods = [n for n in bridge.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in methods} == names
    cls = ast.ClassDef(name='BridgeUnderTest', bases=[], keywords=[], body=methods, decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    namespace = dict(vars(shell))
    exec(compile(module, str(Path(shell.__file__)), 'exec'), namespace)
    return namespace['BridgeUnderTest']


def host(tmp_path, monkeypatch):
    monkeypatch.setattr(shell, 'app_data', lambda: tmp_path)
    settings_file = tmp_path / 'settings.json'
    Settings().save(settings_file)
    instance = bridge_class()()
    instance.settings_file = settings_file
    instance.cancel_chat = threading.Event()
    instance.turn = None
    instance._emit = Mock()
    instance._warm = Mock()
    instance._digest_when_idle = Mock()
    instance.comfy_launcher = SimpleNamespace(start=Mock())
    return instance


def test_real_run_chat_plain_message_uses_provider_and_no_missing_display_prompt(tmp_path, monkeypatch):
    instance = host(tmp_path, monkeypatch)
    provider = Mock(return_value='A normal reply')
    monkeypatch.setattr(shell, 'run_task', provider)
    monkeypatch.setattr(shell, 'provider_kind', lambda settings: 'local')
    monkeypatch.setattr(shell, 'prepare_turn', lambda *a, **kw: SimpleNamespace(
        pictures=[], documents=[], footer='', prompt=lambda text: text))
    result = instance._run_chat('request', 'Hello STAR', [])
    assert result['answer'] == 'A normal reply'
    assert provider.call_args.args[1] == 'Hello STAR'
    chats = Conversations(tmp_path / 'conversations.sqlite3')
    try:
        chat_id = chats.active_chat(Settings().project)
        records = chats.recent_records(Settings().project, chat_id=chat_id)
        assert [(row['role'],row['body']) for row in records][-2:] == [
            ('user','Hello STAR'),('assistant','A normal reply')]
    finally:
        chats.close()


def test_real_run_image_starts_engine_and_preserves_display_text(tmp_path, monkeypatch):
    instance = host(tmp_path, monkeypatch)
    settings = Settings.load(instance.settings_file)
    settings.comfy_home = str(tmp_path)
    settings.save(instance.settings_file)
    monkeypatch.setattr(shell.image_gen, 'status', lambda settings: {'running': False})
    generator = Mock(return_value={'answer':'Created', 'image':'data:image/png;base64,AA==',
                                   'message':'STAR_GENERATED_IMAGE:picture.png'})
    monkeypatch.setattr(shell, 'generate_chat_image', generator)
    result = instance._run_image('request','a dog',display_prompt='Generate an image of a dog')
    assert result['answer'] == 'Created'
    instance.comfy_launcher.start.assert_called_once()
    generator.assert_called_once()
    assert any('Starting the image engine' in str(c) for c in instance._emit.call_args_list)
    chats = Conversations(tmp_path/'conversations.sqlite3')
    try:
        chat_id = chats.active_chat(settings.project)
        records = chats.recent_records(settings.project, chat_id=chat_id)
        assert [(r['role'], r['body']) for r in records][-2:] == [
            ('user','Generate an image of a dog'),('assistant','STAR_GENERATED_IMAGE:picture.png')]
    finally:
        chats.close()


def test_real_run_image_without_setup_returns_settings_instruction(tmp_path, monkeypatch):
    instance = host(tmp_path, monkeypatch)
    monkeypatch.setattr(shell.image_gen, 'status', lambda settings: {'running': False})
    monkeypatch.setattr(shell, 'generate_chat_image', Mock(side_effect=AssertionError('engine called')))
    result = instance._run_image('request','a picture')
    assert 'Settings' in result['answer']


def test_real_run_image_followup_reuses_saved_picture(tmp_path, monkeypatch):
    instance = host(tmp_path, monkeypatch)
    monkeypatch.setattr(shell.image_gen, 'status', lambda settings: {'running': True})
    folder = tmp_path/'generated-images'
    folder.mkdir()
    path = folder/'picture.png'
    path.write_bytes(b'png bytes')
    settings = Settings.load(instance.settings_file)
    chats = Conversations(tmp_path/'conversations.sqlite3')
    try:
        chat_id = chats.active_chat(settings.project)
        chats.add(settings.project,'assistant','STAR_GENERATED_IMAGE:picture.png',chat_id=chat_id)
    finally:
        chats.close()
    generator = Mock(return_value={'answer':'Edited','image':'data:image/png;base64,AA==',
                                   'message':'STAR_GENERATED_IMAGE:edited.png'})
    monkeypatch.setattr(shell, 'generate_chat_image', generator)
    result = instance._run_image('request','make it brown',followup=True)
    assert result['answer'] == 'Edited'
    assert generator.call_args.kwargs['source'] == path.resolve()
