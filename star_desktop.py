"""STAR Desktop executable entry point.

The --doctor command is supported in headless Windows CI to check the packaged app.
"""
import sys
import os


def main():
    if '--build-doctor' in sys.argv:
        from star.build_info import read_build_info
        result = read_build_info()
        expected = os.environ.get("STAR_EXPECTED_HEAD_SHA", "").strip()
        if not result["stamped"]:
            raise RuntimeError("Packaged source provenance is missing or malformed")
        if expected and result["head_commit"] != expected:
            raise RuntimeError("Packaged source does not match the expected GitHub review commit")
        print("STAR exact build:", result["head_commit"], result["run_url"])
        return 0
    if '--doctor' in sys.argv:
        from star.desktop_core import Settings, app_data
        from star.media import image_part
        from star.version import __version__
        from star.build_info import read_build_info
        print(f'STAR v{__version__} packaged backend OK')
        build=read_build_info()
        print('Build source:',build['head_commit'][:12] if build['stamped'] else 'local source / unstamped')
        print('Local data:', app_data())
        Settings().validate()
        # Packaged Windows binaries must include the OS-backed credential
        # provider; discovery can otherwise appear to work but key saving fails.
        if sys.platform == 'win32':
            from keyring.backends.Windows import WinVaultKeyring
            if WinVaultKeyring is None:
                raise RuntimeError('Windows credential vault backend missing')
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
