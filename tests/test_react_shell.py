"""Release-level checks independent of React's node runtime."""
from pathlib import Path
from star.react_desktop import frontend_path, sanitize_new_settings, state_snapshot
from star.desktop_core import Settings

ROOT = Path(__file__).resolve().parents[1]

def test_react_source_has_real_local_bridge_and_access_scopes():
    js = (ROOT / 'frontend/src/lib/bridge.ts').read_text()
    api = (ROOT / 'star/react_desktop.py').read_text()
    assert 'QWebChannel' in api and 'starBridge' in api
    assert "action == 'chat_send'" in api
    assert "action == 'studio_discover'" in api
    assert 'open_url' in api and 'https://github.com/oncoursemail/Star-AI/' in api
    assert 'window.qt?.webChannelTransport' in js
    assert 'new window.QWebChannel!' in js


def test_state_settings_are_whitelisted():
    import pytest
    with pytest.raises(ValueError):
        sanitize_new_settings(Settings(), {'developer_mode_unrestricted': True})
    assert sanitize_new_settings(Settings(), {'project': 'VALEN'}).project == 'VALEN'


def test_frontend_build_is_integrated_in_windows_release():
    workflow = (ROOT / '.github/workflows/windows-desktop.yml').read_text()
    assert 'frontend/dist' in workflow
    assert 'npm run build' in workflow
    assert '--add-data' in workflow


def test_frontend_path_can_be_missing_from_unbuilt_checkout():
    value = frontend_path()
    assert value is None or value.name == 'index.html'
