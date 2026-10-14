"""Optional StyLua formatting for model-generated Luau, never enabled implicitly.

The caller chooses to use an already installed local StyLua executable. It
receives source on stdin, cannot rewrite arbitrary project paths, and has a
finite execution and output budget. The builder independently revalidates it.
"""
from __future__ import annotations

import shutil
import subprocess
from typing import Callable


MAX_CODE_BYTES = 120_000
FORMAT_TIMEOUT_SECONDS = 10


def installed_formatter() -> Callable[[str], str]:
    """Return an opt-in formatter, or refuse before generation if unavailable."""
    executable = shutil.which("stylua")
    if not executable:
        raise ValueError("StyLua is not installed on PATH; --stylua was not enabled.")

    def format_generated(source: str) -> str:
        if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_CODE_BYTES:
            raise ValueError("Generated Luau exceeds the StyLua input limit")
        try:
            result = subprocess.run(
                [executable, "--syntax", "Luau", "--indent-type", "Spaces",
                 "--indent-width", "4", "--line-endings", "Unix",
                 "--no-editorconfig", "-"],
                input=source, capture_output=True, text=True, encoding="utf-8",
                timeout=FORMAT_TIMEOUT_SECONDS, check=False,
            )
        except (OSError, UnicodeError, subprocess.TimeoutExpired):
            # External process output may include arbitrary input or local paths.
            raise ValueError("StyLua could not finish formatting") from None
        output = result.stdout
        if (result.returncode != 0 or not isinstance(output, str)
                or not output.strip() or "\x00" in output
                or len(output.encode("utf-8")) > MAX_CODE_BYTES):
            raise ValueError("StyLua rejected the generated Luau")
        return output

    return format_generated
