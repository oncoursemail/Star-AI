"""Execute the checked-in Windows test step with controlled command exit codes."""
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize("pytest_exit,compile_exit", [(0, 0), (1, 0), (5, 0), (0, 1)])
def test_windows_offline_step_preserves_failures(tmp_path, pytest_exit, compile_exit):
    shell = shutil.which("pwsh")
    if shell is None:
        pytest.skip("PowerShell 7 (pwsh) is not installed or not on PATH")
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/windows-desktop.yml"
    text = workflow.read_text(encoding="utf-8")
    step = text.split("      - name: Run offline tests\n", 1)[1].split("      - name:", 1)[0]
    run = textwrap.dedent(step.split("        run: |\n", 1)[1])
    # The real step is executed unchanged. Only Python's exit codes are stubbed;
    # no nested pytest process, package installation or network request is made.
    stub = """
$ErrorActionPreference = 'Stop'
function python {
    if ($args[0] -ne '-m') { throw 'Unexpected command' }
    if ($args[1] -eq 'pytest') {
        Write-Output 'pytest-reached'
        $global:LASTEXITCODE = PYTEST_EXIT
    } elseif ($args[1] -eq 'compileall') {
        Write-Output 'compileall-reached'
        $global:LASTEXITCODE = COMPILE_EXIT
    } else { throw 'Unexpected Python module' }
}
""".replace("PYTEST_EXIT", str(pytest_exit)).replace("COMPILE_EXIT", str(compile_exit))
    completed = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command",
                                stub + run + "\nexit $LASTEXITCODE\n"],
                               cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert "pytest-reached" in completed.stdout
    if pytest_exit:
        assert completed.returncode != 0
        assert "Offline tests failed" in completed.stderr
        assert "compileall-reached" not in completed.stdout
    else:
        assert completed.returncode == compile_exit
        assert "compileall-reached" in completed.stdout


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_windows_offline_step_skips_without_pwsh_on_path(monkeypatch, tmp_path, platform):
    """Even a Windows PC without PowerShell 7 must skip rather than fail."""
    def missing_pwsh(executable):
        assert executable == "pwsh"
        return None

    with monkeypatch.context() as patch:
        patch.setattr(sys, "platform", platform)
        patch.setattr(shutil, "which", missing_pwsh)
        with pytest.raises(pytest.skip.Exception, match=r"PowerShell 7 \(pwsh\) is not installed or not on PATH"):
            test_windows_offline_step_preserves_failures(tmp_path, 0, 0)
