"""React source/host checks without requiring Qt imports on Linux."""
from pathlib import Path
from star.react_shell import ALLOWED_ACTIONS, react_index

ROOT=Path(__file__).resolve().parents[1]

def test_react_native_bridge_commands_are_explicit():
    assert 'sendMessage' in ALLOWED_ACTIONS
    assert 'installBrain' in ALLOWED_ACTIONS
    assert 'discoverStudio' in ALLOWED_ACTIONS
    assert 'run_arbitrary_shell' not in ALLOWED_ACTIONS

def test_react_web_sources_exist():
    assert (ROOT/'frontend/src/App.tsx').is_file()
    assert (ROOT/'frontend/src/Desktop.tsx').is_file()
    assert (ROOT/'frontend/src/bridge.ts').is_file()
    assert (ROOT/'frontend/src/styles.css').is_file()

def test_windows_workflow_builds_react_assets():
    workflow=(ROOT/'.github/workflows/windows-desktop.yml').read_text()
    assert 'frontend/dist' in workflow
    assert 'npm run build' in workflow
    assert '--add-data' in workflow
