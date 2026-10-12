"""Source-only acceptance assertions for the external Brain 2 MCP client probe.

No Roblox launcher, MCP process, network, keyring or graphics is required.
"""
import pytest

from scripts.brain2_mcp_smoke import report_for


def test_probe_requires_real_selected_stdio_status_and_read_tool():
    catalog = ["star_connection_status", "script_read", "multi_edit"]
    status = {"status": "tools_and_instances_discovered", "selected": {
        "id": "private-studio-id", "name": "private-place"},
        "local_mcp": "stdio"}
    report = report_for(catalog, status)
    assert report["connection"] == "verified_via_stdio"
    assert report["read_tools_available"] == ["script_read"]
    assert report["approved_tool_count"] == 2
    assert "private-studio-id" not in str(report)
    assert "private-place" not in str(report)
    assert "Brain 2" in report["notice"]


@pytest.mark.parametrize(("catalog", "status"), [
    (["star_connection_status", "script_read"],
     {"status": "tools_discovered_no_instances", "selected": None, "local_mcp": "stdio"}),
    (["star_connection_status", "script_read"],
     {"status": "tools_and_instances_discovered", "selected": None, "local_mcp": "stdio"}),
    (["star_connection_status", "script_read"],
     {"status": "tools_and_instances_discovered", "selected": "one", "local_mcp": "memory"}),
    (["script_read"],
     {"status": "tools_and_instances_discovered", "selected": "one", "local_mcp": "stdio"}),
    (["star_connection_status", "multi_edit"],
     {"status": "tools_and_instances_discovered", "selected": "one", "local_mcp": "stdio"}),
])
def test_probe_rejects_incomplete_or_not_source_stdio_connection(catalog, status):
    with pytest.raises(RuntimeError):
        report_for(catalog, status)
