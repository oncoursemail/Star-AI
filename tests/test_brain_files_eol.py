"""STAR Brain files go to a Linux server unchanged, so a Windows checkout must keep them LF."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_gitattributes_keeps_brain_files_lf():
    assert "server/brain/** text eol=lf" in (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()


def test_brain_models_ini_is_checked_out_with_lf():
    try:
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "server/brain/models.ini"], cwd=ROOT,
                                 capture_output=True).returncode == 0
    except OSError:
        tracked = False
    if not tracked:
        return              # a source copy without git: nothing to say about the checkout
    data = (ROOT / "server" / "brain" / "models.ini").read_bytes()
    # A checkout made before the rule may still be CRLF until it is refreshed; the index must be LF either way.
    index = subprocess.run(["git", "show", ":server/brain/models.ini"], cwd=ROOT, capture_output=True).stdout
    assert b"\r\n" not in index
    assert data.replace(b"\r\n", b"\n") == index
