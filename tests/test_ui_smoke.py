"""The Windows action runs a real offscreen Qt construction smoke test."""
import os
import pytest


def test_desktop_creates_all_pages_without_a_model(monkeypatch,tmp_path):
    pytest.importorskip('PySide6')
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    monkeypatch.setenv('APPDATA',str(tmp_path))
    from PySide6.QtWidgets import QApplication
    from star.desktop import MainWindow
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    assert window.pages.count()==7
    from star.version import __version__
    assert __version__ in window.windowTitle()
    assert window.brain_page is not None
    assert window.install_brain_button.isEnabled()
    assert window.analytics_page is not None
    window.show_page(6)
    assert window.metric_cards['started'].value.text()=='0'
    assert window.activity_chart is not None
    window.show_page(0)
    assert window.hero is not None
    assert window.prompt.accessibleName() == 'Message STAR'
    snapshot=tmp_path/'star-ui-test.png'
    assert window.grab().save(str(snapshot)) and snapshot.stat().st_size>1000
    window.close()
