"""Built-in, scalable vector icons and a deliberately restrained cosmic identity."""
from __future__ import annotations

ICONS = {
    'chat': '<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 10 10 0 0 1-4-.8L3 21l1.8-5a9 9 0 1 1 16.2-4.5Z"/>',
    'projects': '<rect x="3" y="3" width="7" height="7" rx="1.3"/><rect x="14" y="3" width="7" height="7" rx="1.3"/><rect x="3" y="14" width="7" height="7" rx="1.3"/><rect x="14" y="14" width="7" height="7" rx="1.3"/>',
    'tools': '<path d="M14.5 6.5a5 5 0 0 0-6.6 6.6L3 18l3 3 4.9-4.9a5 5 0 0 0 6.6-6.6L14 13l-3-3z"/>',
    'image': '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.3"/><path d="m3 17 5-5 4 4 4-6 5 7"/>',
    'settings': '<path d="M12 2v3m0 14v3M4.93 4.93l2.12 2.12m9.9 9.9 2.12 2.12M2 12h3m14 0h3M4.93 19.07l2.12-2.12m9.9-9.9 2.12-2.12"/><circle cx="12" cy="12" r="4"/>',
    'brain': '<path d="M12 4a4 4 0 0 0-7 3 4.5 4.5 0 0 0-.7 7.5A4 4 0 0 0 9 21c1.5 0 3-1 3-3V4Zm0 0a4 4 0 0 1 7 3 4.5 4.5 0 0 1 .7 7.5A4 4 0 0 1 15 21c-1.5 0-3-1-3-3V4Z"/><path d="M8 10h4m0 5h4"/>',
    'download': '<path d="M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4"/>',
    'refresh': '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M5 9A8 8 0 0 1 19 7l1 5M4 12l1 5a8 8 0 0 0 14-2"/>',
    'check': '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    'cpu': '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3"/>',
    'mic': '<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 11a7 7 0 0 0 14 0m-7 7v4m-4 0h8"/>',
    'paperclip': '<path d="m21.4 11.6-8.8 8.8a6 6 0 0 1-8.5-8.5l9.5-9.5a4 4 0 0 1 5.7 5.7l-9.9 9.9a2 2 0 0 1-2.8-2.8l8.8-8.8"/>',
    'arrow': '<path d="M12 19V5m-6 6 6-6 6 6"/>',
    'github': '<path d="M9 19c-4 1-4-2-6-2m14 4v-3a3 3 0 0 0-.9-2.3c3-.3 6.1-1.5 6.1-6.7a5.2 5.2 0 0 0-1.4-3.6A4.8 4.8 0 0 0 20.6 2S19 2 17 3.6a14 14 0 0 0-10 0C5 2 3.4 2 3.4 2a4.8 4.8 0 0 0-.2 3.4A5.2 5.2 0 0 0 1.8 9c0 5.2 3.1 6.4 6.1 6.7A3 3 0 0 0 7 18v3"/>',
    'rocket': '<path d="M6 17 3 21l5-2m9-13a10 10 0 0 0-9 9l-2 2 1 1 2-2a10 10 0 0 0 9-9l2-4-4 2Z"/><circle cx="15" cy="9" r="2"/>',
    'external': '<path d="M13 4h7v7M20 4l-9 9"/><path d="M20 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h5"/>',
    'shield': '<path d="m12 2 9 4v6c0 6-4 9-9 10-5-1-9-4-9-10V6z"/><path d="m8 12 3 3 5-6"/>',
    'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
    'analytics': '<path d="M3 20h18M5 16l4-5 4 3 6-8"/><path d="M17 6h2v2"/>',
    'sound': '<path d="M3 10v4h4l5 4V6l-5 4H3Zm12-1a5 5 0 0 1 0 6m2-9a9 9 0 0 1 0 12"/>',
    'copy': '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
    'new': '<path d="M12 5v14m-7-7h14"/>',
}

BRAND_PATH = 'M24 3 29.4 18.6 45 24 29.4 29.4 24 45 18.6 29.4 3 24 18.6 18.6Z'


def svg_icon(name: str, color: str = '#d6c79f', size: int = 24) -> str:
    """SVG stroke icon strings; no font dependence or asset fetching."""
    if name == 'star':
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 48 48">'
                f'<path fill="{color}" d="{BRAND_PATH}"/></svg>')
    if name not in ICONS:
        raise KeyError(name)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
            f'{ICONS[name]}</svg>')


def qt_icon(name: str, color: str = '#e8c66e', size: int = 22):
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QIcon, QPixmap, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtCore import Qt
    data = svg_icon(name, color, size).encode('utf-8')
    renderer = QSvgRenderer(QByteArray(data))
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return QIcon(pix)
