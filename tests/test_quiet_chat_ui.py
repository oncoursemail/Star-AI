"""Guard the conversation-first, one-window STAR design against old UI regressions."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def chat_ui():
    """The chat screen is Desktop.tsx (state and wiring) plus the composer it renders."""
    return read("frontend/src/Desktop.tsx") + read("frontend/src/Composer.tsx")


def desktop_css():
    """Desktop styles: one token file, the shell chrome, and the chat. Whitespace-insensitive."""
    return "".join(read("frontend/src/" + name) for name in
                   ("tokens.css", "stellar-ui.css", "chat.css")).replace(" ", "")


def test_inline_image_generation_not_separate_lab():
    ui = chat_ui()
    assert "tab==='image'" not in ui
    assert "Image Lab" not in ui
    assert "Create image" in ui
    assert "imageMode?'generateImage':teamMode?'runTeam':'sendMessage'" in ui
    assert "comfy_workflow" in ui
    assert "openLegacy" not in ui


def test_clean_chat_composition_and_real_threads():
    ui = chat_ui()
    assert "startNewChat" in ui and "switchChat" in ui
    assert "filteredChats" in ui and "historySearchOpen" in ui
    assert "composer-menu" in ui and "composer-image-chip" in ui
    assert "sidebarCollapsed" in ui
    assert "chat-jump" in ui and "followBottom" in ui


def test_persistent_image_message_preview():
    host = read("star/react_shell.py")
    core = read("star/desktop_core.py")
    chat = read("star/chat_images.py")
    component = read("frontend/src/components.tsx")
    assert "chat_image(home, body)" in host
    assert "chat_id=chat_id" in host
    assert "result['message']" in host
    assert "comfy_workflow" in core and "comfy_prompt_node" in core
    assert "generated-images" in chat
    assert "generated-image-button" in component
    assert "Dialog.Content" in component


def test_reduced_motion_and_ui_research():
    ui = read("frontend/src/Desktop.tsx")
    css = desktop_css()
    assert "MotionConfig reducedMotion" in ui
    assert "prefers-reduced-motion" in css
    assert "flex-direction:row" in css
    assert "window.matchMedia" in ui
    # STAR's own Reduced motion setting reaches CSS transitions too, and is stored at once.
    assert "data-reduced-motion={!themeMotion}" in ui
    assert ".shell[data-reduced-motion='true']" in read("frontend/src/tokens.css")
    assert "act('saveSettings',{settings:{reduced_motion:reduced}})" in ui


def test_one_token_source_and_no_orphan_desktop_stylesheets():
    tokens = read("frontend/src/tokens.css")
    for name in ("--star-bg", "--star-surface-2", "--star-gold", "--star-dur-hover", "--star-read"):
        assert name + ":" in tokens
    # Chat and shell styles take every colour from the tokens: no palette of their own.
    import re
    for sheet in ("chat.css", "stellar-ui.css"):
        css = read("frontend/src/" + sheet)
        assert not re.findall(r"#[0-9a-fA-F]{3,8}|rgba?\(", css), sheet
    # Stylesheets that nothing imported were removed rather than left to drift.
    assert not (ROOT / "frontend/src/desktop-v2.css").exists()
    assert not (ROOT / "frontend/src/agents-learning.css").exists()


def test_chat_controls_are_wired_to_real_actions():
    ui = chat_ui()
    # Starter prompts fill the composer; Stop cancels the real backend task.
    assert "fillComposer(item.prompt)" in ui
    assert "act('cancelMessage')" in ui
    # A request the host refuses keeps the question on screen with Retry and Edit.
    assert "updateRun(null);setBusy(false);setRetryText(value)" in ui
    # Retry survives a restart through the host's retry record, and re-sends that prompt.
    assert "const retryPrompt=retryText||pending?.prompt||''" in ui
    # The second click of a double-click on Send must not land on Stop and cancel the turn.
    assert "if (event.detail > 1) return" in ui
    # The timeline is reduced from backend progress events, never from a timer.
    assert "applyProgress(runRef.current,info,Date.now())" in ui
    assert "setInterval" not in read("frontend/src/activity.ts")


def test_preview_fixtures_cannot_reach_the_desktop_path():
    ui = read("frontend/src/Desktop.tsx")
    # Only a type import is static; the data loads by dynamic import in browser preview.
    assert "import type {Fixture,FixtureScript} from './previewFixtures'" in ui
    assert ui.count("from './previewFixtures'") == 1
    assert "import('./previewFixtures')" in ui
    assert "if(!preview||window.qt?.webChannelTransport)return ''" in ui
    for name in ("components.tsx", "Composer.tsx", "ActivityTimeline.tsx", "activity.ts",
                 "connection.ts", "App.tsx", "main.tsx"):
        assert "previewFixtures" not in read("frontend/src/" + name), name
    assert "Preview fixture" in ui
