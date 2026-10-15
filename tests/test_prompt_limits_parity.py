"""The composer's prompt limits (frontend/src/promptLimits.ts) match what the host refuses (star/react_shell.py)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def _frontend_limits() -> dict[str, int]:
    source = (ROOT / "frontend" / "src" / "promptLimits.ts").read_text(encoding="utf-8")
    block = re.search(r"PROMPT_LIMITS\s*=\s*\{([^}]*)\}", source).group(1)
    return {key: int(value) for key, value in re.findall(r"(\w+)\s*:\s*(\d+)", block)}


def _host_source() -> str:
    return (ROOT / "star" / "react_shell.py").read_text(encoding="utf-8")


def test_frontend_limits_match_the_host_checks():
    limits = _frontend_limits()
    host = _host_source()
    assert limits == {"chat": 30000, "team": 12000, "image": 1500}
    assert f"len(prompt)>{limits['chat']}" in host                    # sendMessage
    assert f"2 <= len(prompt) <= {limits['team']}" in host             # runTeam
    assert f"1<=len(prompt)<={limits['image']}" in host                # generateImage
