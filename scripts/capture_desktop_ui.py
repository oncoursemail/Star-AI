"""Capture the actual Qt application surfaces on Windows CI for visual review.

The CI viewport has no real model / user data; screenshots are labelled as
empty-state renders, not a claim of successful GPU or Roblox functionality.
"""
from __future__ import annotations
import os
from pathlib import Path
import sys

# Direct execution can start inside scripts/, so ensure the project package is visible.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    from star.desktop import MainWindow
    app=QApplication.instance() or QApplication([])
    output=Path(os.environ.get('STAR_UI_PREVIEW_DIR','ui-previews'))
    output.mkdir(parents=True,exist_ok=True)
    window=MainWindow()
    window.resize(1440,900)
    window.show()
    app.processEvents()
    for name,index in [('chat',0),('analytics',6),('brain',5)]:
        window.show_page(index)
        app.processEvents()
        path=output / f'{name}-1440x900.png'
        if not window.grab().save(str(path)):
            raise RuntimeError('Qt screenshot capture failed for '+name)
    window.resize(1050,680)
    window.show_page(0)
    app.processEvents()
    if not window.grab().save(str(output/'chat-1050x680.png')):
        raise RuntimeError('Compact viewport screenshot capture failed')
    window.close()
    print('STAR Qt screenshot previews:',*[p.name for p in sorted(output.glob('*.png'))])
    return 0


if __name__=='__main__':
    sys.exit(main())
