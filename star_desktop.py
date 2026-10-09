"""STAR Windows executable entry point; React shell with safe legacy fallback."""
import sys


def main():
    if '--doctor' in sys.argv:
        from star.desktop_core import Settings, app_data
        from star.version import __version__
        from star.react_desktop import frontend_path
        Settings().validate()
        if getattr(sys, 'frozen', False) and frontend_path() is None:
            raise RuntimeError('STAR React assets missing from Windows executable')
        print(f'STAR v{__version__} packaged backend OK; React UI:', bool(frontend_path()))
        print('Local data:', app_data())
        return 0
    from star.react_desktop import frontend_path
    if frontend_path() is not None:
        from star.react_desktop import launch
        launch()
    else:
        # Source-only fallback until frontend npm install && npm run build.
        from star.desktop import launch
        launch()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
