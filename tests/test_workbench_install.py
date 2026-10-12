"""Offline installer contracts, including executed fail-closed/log-filter branches.

These are not a claim that nftables/systemd/namespaces were deployed on this host.
"""
import ipaddress
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys

import pytest

FOLDER = Path(__file__).parents[1] / "server/workbench"
pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux deployment scripts")


def test_scripts_parse_and_refuse_model_container_before_any_privileged_operation(tmp_path):
    marker = tmp_path / "model-secrets"
    marker.mkdir()
    for filename in ("install.sh", "tunnel.sh"):
        text = (FOLDER / filename).read_text()
        assert "separate" in text.lower().splitlines()[1]
        assert text.index("/opt/star/secrets") < text.index("$EUID")
        subprocess.run(["bash", "-n", str(FOLDER / filename)], check=True)
        # Relocate ONLY the sentinel so the actual refusal branch executes rootlessly.
        staged = tmp_path / filename
        staged.write_text(text.replace("/opt/star/secrets", str(marker)))
        result = subprocess.run(["bash", str(staged)], capture_output=True, text=True)
        assert result.returncode == 1 and "Refusing model/secrets container" in result.stderr


def test_firewall_contract_blocks_required_ranges_before_public_https():
    text = (FOLDER / "install.sh").read_text()
    block = text[text.index(" table inet star_workbench"):text.index("chmod 600 /etc/star-workbench/egress.nft")]
    networks = [ipaddress.ip_network(s) for s in re.findall(r"\d+\.\d+\.\d+\.\d+/\d+", block)]
    assert len(networks) >= 10
    # Required ranges, specified arithmetically: these aren't any owner's LAN address.
    for first, second, prefix in ((10, 0, 8), (172, 16, 12), (192, 168, 16), (169, 254, 16), (100, 64, 10)):
        expected = ipaddress.ip_network((first * 2**24 + second * 2**16, prefix))
        assert expected in networks
        for boundary in (expected.network_address, expected.broadcast_address):
            assert any(boundary in network for network in networks)
    assert block.index("ip daddr {") < block.index("tcp dport 443 accept")
    assert "meta nfproto ipv6 reject" in block
    assert "udp dport 53 accept" in block and "tcp dport 53 accept" in block
    assert "ct state established,related accept" in block  # origin replies work
    assert "meta skuid $WORK_UID reject" in block
    assert "flush ruleset" not in text
    assert "Requires=star-workbench-firewall.service" in text
    assert "systemctl enable --now star-workbench-firewall.service" in text


def test_credentials_service_limits_and_preparation_contract():
    text = (FOLDER / "install.sh").read_text()
    for required in ("User=star-workbench", "NoNewPrivileges=yes", "CapabilityBoundingSet=",
                     "LoadCredential=token:/etc/star-workbench/token", "ProtectSystem=strict",
                     "KillMode=control-group", "MemoryMax=4G", "TasksMax=384", "CPUQuota=200%",
                     "openssl rand -hex 32 > /etc/star-workbench/token", "chmod 600 /etc/star-workbench/token",
                     "runuser -u star-workbench", "app.py --prepare", "StandardError=null"):
        assert required in text
    assert text.index("set +x") < text.index("openssl rand")
    assert "cat /etc/star-workbench/token" not in text
    assert "ProtectHome=yes" in text and "PrivateDevices=yes" in text


def test_tunnel_pinned_checksum_and_current_invocation_url():
    text = (FOLDER / "tunnel.sh").read_text()
    assert "VERSION=2026.10.0" in text
    pins = re.findall(r"SHA=([a-f0-9]{64})", text)
    assert len(set(pins)) == 2
    assert text.index("sha256sum --check --status") < text.index("install -o root -g root -m 755")
    assert "https://github.com/cloudflare/cloudflared/releases/download/$VERSION/" in text
    assert "--no-autoupdate" in text and "http://127.0.0.1:8765" in text
    assert '"_SYSTEMD_INVOCATION_ID=$INVOCATION"' in text
    assert "User=star-workbench-tunnel" in text
    assert "InaccessiblePaths=/work /etc/star-workbench" in text


def test_tunnel_filter_never_forwards_request_credentials(tmp_path):
    text = (FOLDER / "tunnel.sh").read_text()
    secret = secrets.token_hex(32)
    executable = tmp_path / "fake-cloudflared"
    executable.write_text("#!/bin/sh\nprintf '%s\\n' " +
                          "'INF | https://fixture.trycloudflare.com |' " +
                          f"'ERR request https://fixture.trycloudflare.com/mcp/{secret}/ Authorization: Bearer {secret}' " +
                          "'ERR request https://unrelated.trycloudflare.com/path'\n")
    executable.chmod(0o700)
    # Only substitute external dependencies/UID test, not the logging pipeline.
    staged = tmp_path / "tunnel.sh"
    text = text.replace("/usr/local/bin/star-cloudflared", str(executable))
    text = text.replace("/opt/star/secrets", str(tmp_path / "absent"))
    text = text.replace("[[ $EUID -ne 0 ]]", "[[ 1 -ne 0 ]]")
    staged.write_text(text)
    result = subprocess.run(["bash", str(staged), "serve"], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "https://fixture.trycloudflare.com"
    assert secret not in result.stdout + result.stderr


def test_private_install_publishes_read_only_server_venv(tmp_path):
    text = (FOLDER / "install.sh").read_text()
    command = next(line for line in text.splitlines() if line.startswith("chmod -R go-w,go+rX "))
    assert command.split()[-1] == "/opt/star-workbench/venv"
    assert text.index("venv/bin/pip install") < text.index(command) < text.index("runuser -u")
    runtime = tmp_path / "venv"
    subprocess.run(["bash", "-c", 'umask 077; exec "$@"', "venv-fixture",
                    sys.executable, "-m", "venv", "--without-pip", str(runtime)], check=True)
    assert runtime.stat().st_mode & 0o077 == 0  # Reproduces the actual installer failure.
    module = next(runtime.glob("lib/python*/site-packages")) / "fixture.py"
    module.write_text("VALUE = 42\n")
    module.chmod(0o600)
    # venv copies some upstream script modes, independently of the private umask.
    (runtime / "bin/Activate.ps1").chmod(0o777)
    token = tmp_path / "token"
    token.write_text(secrets.token_hex(32))
    token.chmod(0o600)
    # Execute the installer's exact chmod command, changing only its destination.
    subprocess.run([*command.split()[:-1], str(runtime)], check=True)
    for entry in [runtime, *runtime.rglob("*")]:
        if entry.is_symlink():
            continue  # Never chmod the system interpreter behind a venv symlink.
        mode = entry.stat().st_mode
        assert mode & 0o022 == 0, f"runtime is writable by another account: {entry}"
        required = 0o055 if entry.is_dir() else 0o044
        assert mode & required == required, f"runtime is unreadable to the service: {entry}"
    assert token.stat().st_mode & 0o777 == 0o600
