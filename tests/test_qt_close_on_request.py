"""Offscreen Qt integration regressions for the real React shell close event.

Run with QT_QPA_PLATFORM=offscreen and PySide6 installed. WebEngine is replaced
with an inert QWidget because these checks exercise host lifecycle, not Chromium.
The session case calls the handler, not Windows Restart Manager. The quit case
emits the real Qt aboutToQuit signal; neither case replaces packaged W04b.
"""
import os
import sys
import types

import pytest


@pytest.mark.parametrize("mode", ["idle", "running", "session", "quit"])
def test_real_shell_shutdown_paths(monkeypatch, tmp_path, mode):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    QtCore = pytest.importorskip("PySide6.QtCore")
    import star.react_shell as shell_module
    from star.desktop_core import Conversations

    index = tmp_path / "index.html"
    index.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(shell_module, "react_index", lambda: index)
    monkeypatch.setattr(shell_module, "app_data", lambda: tmp_path)
    monkeypatch.setattr("star.single_instance.bypass_single_instance", lambda: True)

    class FakePage(QtCore.QObject):
        def __init__(self, *args):
            super().__init__()
        def setWebChannel(self, channel):
            pass

    class FakeView(QtWidgets.QWidget):
        def __init__(self, *args):
            super().__init__(*args)
            self._page = None
        def setPage(self, page):
            self._page = page
        def page(self):
            return self._page
        def load(self, url):
            pass

    class FakeChannel:
        def __init__(self, *args):
            pass
        def registerObject(self, *args):
            pass

    monkeypatch.setitem(sys.modules, "PySide6.QtWebEngineCore",
                        types.SimpleNamespace(QWebEnginePage=FakePage))
    monkeypatch.setitem(sys.modules, "PySide6.QtWebEngineWidgets",
                        types.SimpleNamespace(QWebEngineView=FakeView))
    monkeypatch.setitem(sys.modules, "PySide6.QtWebChannel",
                        types.SimpleNamespace(QWebChannel=FakeChannel))

    class Service:
        def __init__(self, *args, **kwargs):
            self.stopped = False
        def close(self):
            self.stopped = True
        def stop(self):
            self.stopped = True
        def cancel(self):
            self.stopped = True

    class Voice(Service):
        def __init__(self, *args, **kwargs):
            super().__init__()

    for name in ("Runtime", "Warmer", "Digester", "ComfyLauncher"):
        monkeypatch.setattr(shell_module, name, Service)
    monkeypatch.setattr(shell_module, "VoiceBridge", Voice)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    seen = []

    def fake_exec():
        window = next(widget for widget in app.topLevelWidgets()
                      if isinstance(widget, QtWidgets.QMainWindow) and widget.isVisible())
        bridge = window.bridge
        if mode != "idle":
            chats = Conversations(tmp_path / "conversations.sqlite3")
            try:
                chat_id = chats.active_chat("default")
                message_id = chats.add("default", "user", "A long fake turn", chat_id=chat_id)
            finally:
                chats.close()
            bridge.turn = shell_module.TurnRef("default", chat_id, message_id)
            bridge.active_task = True
        if mode == "session":
            # Direct handler coverage, not a real commitDataRequest or installer request.
            shell_module.close_for_session(window, object())
        elif mode == "quit":
            app.aboutToQuit.emit()
        else:
            window.close()
        # Exercise the signal connection launch registered, including repeated close.
        app.aboutToQuit.emit()
        assert all(service.stopped for service in
                   (bridge.comfy_launcher, bridge.warmer, bridge.runtime, bridge.voice))
        seen.append((bridge.cancel_chat.is_set(), bridge._closing))
        window.close()
        return 0

    # QApplication.exec is static; a plain function would bind an extra argument.
    monkeypatch.setattr(QtWidgets.QApplication, "exec", staticmethod(fake_exec))
    assert shell_module.launch() == 0
    assert seen == [(True, True)]
    if mode != "idle":
        chats = Conversations(tmp_path / "conversations.sqlite3")
        try:
            state = chats.retry_state("default", chats.active_chat("default"))
            assert state["status"] == "cancelled"
        finally:
            chats.close()
