"""Pin the Inno Setup privilege defaults against surprise elevation regressions."""

from pathlib import Path
import re

import pytest


INSTALLER = Path(__file__).resolve().parents[1] / "installer" / "STAR.iss"


def _setup_values(source: str, directive: str) -> list[str]:
    """Read active values in [Setup], not comments or unrelated sections."""
    start = re.search(r"(?im)^\[setup\][ \t]*\r?$", source)
    if start is None:
        return []
    section = source[start.end():]
    end = re.search(r"(?m)^\[[A-Za-z][A-Za-z0-9_]*\][ \t]*\r?$", section)
    if end is not None:
        section = section[:end.start()]

    values = []
    for line in section.splitlines():
        line = line.strip()
        if not line or line.startswith((";", "#")):
            continue
        key, separator, value = line.partition("=")
        if separator and key.strip().casefold() == directive.casefold():
            values.append(value.strip().casefold())
    return values


def test_installer_defaults_to_no_admin_per_user_mode():
    source = INSTALLER.read_text(encoding="utf-8")
    values = _setup_values(source, "PrivilegesRequired")
    assert values == ["lowest"], f"Expected one per-user privilege setting; got {values!r}"


def test_installer_keeps_all_users_choice_in_privilege_dialog():
    source = INSTALLER.read_text(encoding="utf-8")
    values = _setup_values(source, "PrivilegesRequiredOverridesAllowed")
    assert len(values) == 1, f"Expected one install-scope override; got {values!r}"
    options = set(re.split(r"[\s,]+", values[0]))
    assert "dialog" in options, f"All-users choice must stay in installer dialog; got {values!r}"


def test_manual_setup_preserves_previous_privileges():
    source = INSTALLER.read_text(encoding='utf-8')
    assert _setup_values(source, 'UsePreviousPrivileges') == ['yes']
