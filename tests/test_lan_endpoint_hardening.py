"""Fail-closed LAN endpoint and credential-routing regression tests (offline)."""
from types import SimpleNamespace

import pytest

from star import providers
from star.doc_knowledge import knowledge_endpoint_for, validate_knowledge_endpoint
from star.providers import STAR_SERVER, connection_for, validate_lan_endpoint


@pytest.mark.parametrize("host", [
    "127.0.0.1", "127.255.255.254", "10.0.0.1", "10.255.255.254",
    "172.16.0.1", "172.31.255.254", "192.168.0.1", "192.168.255.254",
    "100.64.0.1", "100.127.255.254",
    "[::1]", "[fc00::1]", "[fd12:3456::1]",
    "[::ffff:127.0.0.1]", "[::ffff:192.168.1.1]", "[::ffff:100.64.1.1]",
])
def test_allowed_lan_ip_ranges(host):
    url = f"http://{host}:8080/v1"
    assert validate_lan_endpoint(url) == url


@pytest.mark.parametrize("host", [
    "localhost", "star-server", "server.local", "server.lan", "server.home.arpa",
    "workstation.office.local", "node-2.lab.home.arpa", "local", "lan",
])
def test_reject_local_dns_names_until_connections_are_pinned(host):
    with pytest.raises(ValueError):
        validate_lan_endpoint(f"https://{host}:8443/v1")


@pytest.mark.parametrize("host", [
    "169.254.0.1", "169.254.169.254", "100.63.255.255", "100.128.0.0",
    "8.8.8.8", "192.0.2.1", "198.51.100.20", "203.0.113.1",
    "198.18.0.1", "0.0.0.0", "255.255.255.255",
    "224.0.0.1", "240.0.0.1",
    "[fe80::1]", "[febf::1]", "[2001:db8::1]", "[2001:4860::1]",
    "[ff02::1]", "[::]", "[::ffff:169.254.169.254]",
    "[::ffff:8.8.8.8]", "[::ffff:192.0.2.1]",
    "[::ffff:255.255.255.255]", "[::ffff:0.0.0.0]",
])
def test_rejected_public_link_local_and_special_addresses(host):
    with pytest.raises(ValueError):
        validate_lan_endpoint(f"http://{host}:8080/v1")


@pytest.mark.parametrize("host", [
    "2130706433", "167772161", "017700000001", "0x7f000001", "0o17700000001",
    "127.1", "10.1", "0177.0.0.1", "0x7f.0.0.1", "0x0a000001",
    "010.0.0.1", "127.0.0.01", "10.0.0.1.",
    "example.com", "metadata.google.internal", "server.local.example.com",
    "server.home.arpa.example", "a..local", "-bad.lan", "bad-.local",
    "foo_bar.local", "tést.local", ".local", "server.",
])
def test_rejected_encoded_ips_and_non_local_dns_names(host):
    with pytest.raises(ValueError):
        validate_lan_endpoint(f"http://{host}:8080/v1")


@pytest.mark.parametrize("endpoint", [
    "http://169.254.169.254:8080/v1",
    "http://[fe80::1]:8080/v1",
    "http://[::ffff:169.254.169.254]:8080/v1",
    "http://203.0.113.10:8080/v1",
    "http://0x7f000001:8080/v1",
    "http://0177.0.0.1:8080/v1",
    "http://metadata.example.com:8080/v1",
    "http://bad_name.local:8080/v1",
    "http://guest@192.168.1.20:8080/v1",
    "http://192.168.1.20:8080/v1?ignored=1",
    "ftp://192.168.1.20:8080/v1",
])
def test_rejected_endpoint_never_reads_or_returns_server_credential(monkeypatch, endpoint):
    lookups = []
    monkeypatch.setattr(providers, "get_api_key", lambda name: lookups.append(name) or "test-only-token")
    with pytest.raises(ValueError):
        connection_for(SimpleNamespace(provider=STAR_SERVER, server_endpoint=endpoint))
    assert lookups == []


def test_knowledge_uses_the_same_rule_and_supports_local_names():
    assert validate_knowledge_endpoint("http://192.168.1.20:8091/") == "http://192.168.1.20:8091"
    assert knowledge_endpoint_for(SimpleNamespace(
        knowledge_endpoint="", server_endpoint="http://192.168.1.20:8080/v1")
    ) == "http://192.168.1.20:8091"
    for endpoint in ("http://169.254.169.254:8091", "http://[fe80::1]:8091",
                     "http://docs.example.com:8091", "http://docs.local:8091"):
        with pytest.raises(ValueError):
            validate_knowledge_endpoint(endpoint)
