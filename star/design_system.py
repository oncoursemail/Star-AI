"""STAR's OLED desktop design system.

A 4px spacing rhythm, one restrained solar-gold accent, dark neutral layers,
regular-weight icons and short, functional transitions. Sources and decisions
are documented in docs/STAR_DESKTOP_UX_RESEARCH.md.
"""
from __future__ import annotations

COLORS = {
    'black': '#08090B',
    'sidebar': '#0C0E11',
    'canvas': '#0F1115',
    'surface': '#16191E',
    'surface_hover': '#20242B',
    'surface_active': '#282A24',
    'stroke': '#2B3037',
    'stroke_focus': '#DAB862',
    'text': '#F2F3F4',
    'muted': '#A0A8B3',
    'tertiary': '#78818C',
    'gold': '#EFCB70',
    'gold_hover': '#FFE09C',
    'gold_ink': '#1B1913',
    'good': '#81C7A3',
    'bad': '#EB9A97',
}

SPACING = (4, 8, 12, 16, 20, 24, 32, 40, 48)
MOTION_MS = {'fast': 120, 'message': 180, 'navigation': 160}


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG relative luminance contrast for opaque RGB colors."""
    def luminance(color):
        vals = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055)/1.055)**2.4 for v in vals]
        return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]
    lighter, darker = sorted([luminance(foreground), luminance(background)], reverse=True)
    return (lighter + .05) / (darker + .05)


def stylesheet() -> str:
    c = COLORS
    # Deliberately avoid multi-color gradients, wide glow/shadows, ornamental rings,
    # neon outlines and color-filled message panes. Native Qt scaling remains enabled.
    return f'''
* {{ font-family: "Segoe UI Variable", "Segoe UI", Arial; font-size: 13px; }}
QMainWindow, QWidget#Root {{ background: {c['black']}; color: {c['text']}; }}
QWidget#Content {{ background: {c['canvas']}; color: {c['text']}; }}
QFrame#Sidebar {{ background: {c['sidebar']}; border-right: 1px solid #1F2329; }}
QFrame#TopBar {{ background: {c['canvas']}; border-bottom: 1px solid #22262B; }}
QFrame#EditorBox {{ background: {c['surface']}; border: 1px solid #3A4149; border-radius: 12px; }}
QFrame#PanelCard {{ background: {c['surface']}; border: 1px solid {c['stroke']}; border-radius: 12px; }}
QFrame#Hero {{ background: {c['surface']}; border: 1px solid {c['stroke']}; border-radius: 14px; }}
QFrame#UserBubble {{ background: #24262B; border: 1px solid #343841; border-radius: 12px; }}
QFrame#StarBubble {{ background: transparent; border: none; }}
QFrame#EventBubble {{ background: #15191C; border: 1px solid #252C2F; border-radius: 8px; }}
QFrame#MetricCard {{ background: {c['surface']}; border: 1px solid {c['stroke']}; border-radius: 11px; }}
QFrame#ComposerRow {{ background: transparent; border: none; }}
QFrame#ActivityPanel {{ background: {c['surface']}; border: 1px solid {c['stroke']}; border-radius: 11px; }}
QLabel#Header {{ color: {c['text']}; font-size: 21px; font-weight: 700; }}
QLabel#HeroTitle {{ color: {c['text']}; font-size: 27px; font-weight: 700; }}
QLabel#Brand {{ color: {c['text']}; font-size: 23px; font-weight: 750; }}
QLabel#Muted {{ color: {c['muted']}; font-size: 12px; }}
QLabel#Small {{ color: {c['tertiary']}; font-size: 11px; }}
QLabel#Status {{ color: {c['muted']}; font-size: 12px; }}
QLabel#Section {{ color: #DADDE2; font-size: 12px; font-weight: 650; }}
QLabel#Version {{ color: {c['gold']}; font-size: 11px; padding: 5px 9px; border: 1px solid #5D4E31; border-radius: 6px; background: #252218; }}
QLabel#MetricValue {{ color: {c['text']}; font-size: 27px; font-weight: 700; }}
QLabel#MetricLabel {{ color: {c['muted']}; font-size: 11px; }}
QLabel#Kicker {{ color: {c['gold']}; font-size: 11px; font-weight: 650; }}
QPushButton {{ background: #23282E; color: {c['text']}; border: 1px solid #343B44; border-radius: 8px; padding: 9px 12px; }}
QPushButton:hover {{ background: #30363E; border: 1px solid #656B73; }}
QPushButton:pressed {{ background: #383B3C; }}
QPushButton:disabled {{ color: #777F8B; background: #191D22; border-color: #2C3137; }}
QPushButton:focus {{ border: 2px solid {c['stroke_focus']}; }}
QPushButton#Primary {{ background: {c['gold']}; color: {c['gold_ink']}; font-weight: 700; border: 1px solid {c['gold']}; padding: 10px 15px; }}
QPushButton#Primary:hover {{ background: {c['gold_hover']}; border-color: {c['gold_hover']}; }}
QPushButton#Primary:pressed {{ background: #CFAA56; }}
QPushButton#Nav {{ text-align: left; border: none; background: transparent; color: #9CA5B0; padding: 11px 14px; font-weight: 550; }}
QPushButton#Nav:hover {{ background: #1B2025; color: {c['text']}; }}
QPushButton#Nav:checked {{ background: {c['surface_active']}; color: {c['text']}; border-left: 2px solid {c['gold']}; border-radius: 6px; font-weight: 650; }}
QPushButton#Subtle {{ border: none; background: transparent; color: {c['muted']}; padding: 6px 9px; }}
QPushButton#Subtle:hover {{ color: {c['text']}; background: #22272E; }}
QTextEdit, QLineEdit, QComboBox, QSpinBox, QListWidget {{ background: #11151A; color: {c['text']}; border: 1px solid #343B44; border-radius: 8px; padding: 8px; selection-background-color: #685834; }}
QTextEdit:focus, QLineEdit:focus, QComboBox:focus, QListWidget:focus {{ border: 1px solid {c['gold']}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: #101419; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #343A43; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QCheckBox {{ color: #DADDE2; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; }}
QProgressBar {{ background: #1B2125; border: 1px solid #343B43; border-radius: 6px; text-align: center; height: 13px; color: {c['text']}; }}
QProgressBar::chunk {{ background: {c['gold']}; border-radius: 5px; }}
QMessageBox {{ background: {c['surface']}; }}
'''
