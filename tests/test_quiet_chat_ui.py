"""Guard the conversation-first, one-window STAR design against old UI regressions."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_inline_image_generation_not_separate_lab():
    ui = read("frontend/src/Desktop.tsx")
    assert "tab==='image'" not in ui
    assert "Image Lab" not in ui
    assert "Create image" in ui
    assert "imageMode?'generateImage':'sendMessage'" in ui
    assert "comfy_workflow" in ui
    assert "openLegacy" not in ui


def test_clean_chat_composition_and_real_threads():
    ui = read("frontend/src/Desktop.tsx")
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
    css = read("frontend/src/stellar-ui.css")
    assert "MotionConfig reducedMotion" in ui
    assert "prefers-reduced-motion" in css
    assert "flex-direction:row" in css
    assert "window.matchMedia" in ui
