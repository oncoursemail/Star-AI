"""STAR Desktop executable entry point.

The --doctor command is supported in headless Windows CI to check the packaged app.
"""
import sys


def main():
    if '--doctor' in sys.argv:
        from star.desktop_core import Settings, app_data
        from star.media import image_part
        from star.version import __version__
        print(f'STAR v{__version__} packaged backend OK')
        print('Local data:', app_data())
        Settings().validate()
        return 0
    if '--ui-doctor' in sys.argv:
        from star.react_shell import react_index
        static = react_index()
        if not static.is_file():
            raise RuntimeError('STAR React interface assets are missing')
        from PySide6.QtWebChannel import QWebChannel
        from PySide6.QtWebEngineWidgets import QWebEngineView
        print('STAR React interface assets available:', static)
        return 0
    if '--legacy-ui' in sys.argv:
        from star.desktop import launch
    else:
        from star.react_shell import launch
    launch()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
