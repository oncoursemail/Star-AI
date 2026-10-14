"""Pure palette/contrast/stylesheet contracts; no Qt runtime is needed."""
import pytest

from star import design_system


def test_contrast_known_extremes_are_symmetric():
    contrast = design_system.contrast_ratio
    assert contrast("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast("#FFFFFF", "#000000") == pytest.approx(21.0)
    assert contrast("#A0A8B3", "#A0A8B3") == pytest.approx(1.0)
    assert contrast("#000000", "#000000") == pytest.approx(1.0)


def test_readable_text_and_focus_colors_on_dark_canvas():
    palette = design_system.COLORS
    assert design_system.contrast_ratio(palette["text"], palette["canvas"]) >= 4.5
    assert design_system.contrast_ratio(palette["stroke_focus"], palette["canvas"]) >= 3.0


@pytest.mark.parametrize("invalid", ["#zzzzzz", "#fff", "not-a-color"])
def test_contrast_rejects_malformed_hex_colors(invalid):
    with pytest.raises(ValueError):
        design_system.contrast_ratio(invalid, "#000000")


def test_contrast_rejects_wrong_input_type():
    with pytest.raises(TypeError):
        design_system.contrast_ratio(None, "#FFFFFF")


def test_stylesheet_has_real_component_selectors_and_states():
    css = design_system.stylesheet()
    assert 'QMainWindow, QWidget#Root' in css
    assert "QFrame#Sidebar" in css
    assert "QFrame#EditorBox" in css
    assert "QPushButton#Primary:hover" in css
    assert "QPushButton:disabled" in css
    assert "QTextEdit:focus" in css
    assert f"border: 1px solid {design_system.COLORS['stroke']}" in css
    assert f"background: {design_system.COLORS['gold']}" in css


def test_stylesheet_reads_current_palette_instead_of_stale_constants(monkeypatch):
    monkeypatch.setitem(design_system.COLORS, "gold", "#123456")
    css = design_system.stylesheet()
    assert "QPushButton#Primary { background: #123456;" in css
    assert "QLabel#Version { color: #123456;" in css


def test_stylesheet_reports_missing_required_palette_entry(monkeypatch):
    monkeypatch.delitem(design_system.COLORS, "text")
    with pytest.raises(KeyError, match="text"):
        design_system.stylesheet()
