"""Bundled Roblox API dataset: provenance, size, canonical form, lookups and the offline refresh script."""
import hashlib
import json
from pathlib import Path
import re

import pytest

from scripts import refresh_roblox_api as refresh
from star import roblox_api_dataset as api
from star.roblox_api_checker import check_luau_api, load_api_dump

DATA = api.DATA


@pytest.fixture(scope="module")
def dataset():
    return api.load()


def test_the_data_file_is_small_valid_and_records_its_official_source():
    raw = DATA.read_bytes()
    assert len(raw) < 5_000_000  # repository file limit
    data = json.loads(raw)
    source = data["StarSource"]
    assert re.fullmatch(r"version-[0-9a-f]{16}", source["clientVersionUpload"])
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", source["studioVersion"])
    assert re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", source["generated"])
    assert source["url"] == f"https://setup.rbxcdn.com/{source['clientVersionUpload']}-Full-API-Dump.json"
    assert len(data["Classes"]) > 800 and len(data["Enums"]) > 500


def test_the_committed_file_is_in_the_scripts_canonical_form(capsys):
    assert refresh.main(["--check"]) == 0
    assert "ok:" in capsys.readouterr().out


def test_the_existing_api_checker_reads_the_bundled_data_unchanged():
    dump = load_api_dump(DATA)
    assert {"Workspace", "Players", "ReplicatedStorage", "TweenService", "PathfindingService"} <= dump.services
    assert {"Destroy", "PivotTo", "Anchored", "AssemblyLinearVelocity"} <= dump.inherited_members["Part"]
    findings = check_luau_api(
        'local p = Instance.new("Prat")\nlocal t = game:GetService("TweenServce")\n'
        'local part = Instance.new("Part")\npart:Destry()\npart.Anchored = true', dump)
    assert [(f.rule_id, f.name) for f in findings] == [
        ("unknown-class", "Prat"), ("unknown-service", "TweenServce"), ("unknown-member", "Destry")]
    assert findings[0].suggestion in dump.classes  # closest spelling by difflib ("Path" here)
    assert [f.suggestion for f in findings[1:]] == ["TweenService", "Destroy"]
    assert api.api_dump().services == dump.services


def test_inheritance_signatures_and_member_kinds(dataset):
    assert dataset.ancestry("Part")[:3] == ["Part", "FormFactorPart", "BasePart"]
    raycast = dataset.member("Workspace", "Raycast")
    assert raycast.class_name == "WorldRoot" and raycast.kind == "Function"
    assert [p[0] for p in raycast.parameters] == ["origin", "direction", "raycastParams"]
    assert raycast.returns == ("RaycastResult?",)
    assert dataset.member("Humanoid", "MoveToFinished").signature() == \
        "Humanoid.MoveToFinished: RBXScriptSignal(reached: bool)"
    assert dataset.member("Part", "Color").signature() == "BasePart.Color: Color3"
    assert dataset.member("Part", "NoSuchMember") is None and dataset.member("NoSuchClass", "Name") is None
    assert "Yields" in dataset.member("Path", "ComputeAsync").tags


def test_deprecations_carry_the_preferred_replacement(dataset):
    assert dataset.deprecation("BodyVelocity") == "LinearVelocity"
    assert dataset.deprecation("BodyGyro") == "AlignOrientation"
    assert dataset.deprecation("MarketplaceService", "GetProductInfo") == "GetProductInfoAsync"
    assert dataset.deprecation("Workspace", "FindPartOnRay") == "Raycast"
    assert dataset.deprecation("Humanoid", "LoadAnimation") is not None
    assert dataset.deprecation("LinearVelocity") is None
    assert dataset.deprecation("WorldRoot", "Raycast") is None
    assert dataset.deprecation("Message") == ""  # deprecated, no replacement named in the dump


def test_services_and_enums(dataset):
    assert {"Players", "DataStoreService", "MarketplaceService", "ConfigService"} <= dataset.services
    assert "Part" not in dataset.services
    assert {"Success", "NoPath"} <= dataset.enums["PathStatus"]
    assert {"Exclude", "Include"} == dataset.enums["RaycastFilterType"]


def test_describe_and_cli(dataset, capsys):
    assert "Deprecated; use GetProductInfoAsync" in dataset.describe("MarketplaceService:GetProductInfo")
    assert dataset.describe("Enum.RaycastFilterType") == "Enum.RaycastFilterType: Exclude, Include"
    assert "service" in dataset.describe("Players")
    with pytest.raises(KeyError):
        dataset.describe("Workspace.NotAThing")
    assert api.main(["WorldRoot.Raycast", "BodyVelocity"]) == 0
    out = capsys.readouterr().out
    assert "WorldRoot:Raycast(" in out and "use LinearVelocity" in out
    assert api.main(["Nope.Nothing"]) == 1
    assert api.main([]) == 2


# ---------------------------------------------------------------- refresh script, offline

def _synthetic_dump(classes=120, enums=60):
    rows = [{"Name": "Instance", "Superclass": "<<<ROOT>>>", "Tags": ["NotCreatable"], "MemoryCategory": "Instances",
             "Members": [
                 {"Name": "Name", "MemberType": "Property", "Category": "Data", "Default": "x",
                  "Serialization": {"CanLoad": True, "CanSave": True}, "ThreadSafety": "ReadSafe",
                  "Security": {"Read": "None", "Write": "None"},
                  "ValueType": {"Category": "Primitive", "Name": "string"}},
                 {"Name": "Remove", "MemberType": "Function", "Parameters": [], "Security": "None",
                  "ReturnType": {"Category": "Primitive", "Name": "null"},
                  "Tags": ["Deprecated", {"PreferredDescriptorName": "Destroy", "ThreadSafety": "Unsafe"}]},
             ]}]
    for i in range(classes - 1):
        rows.append({"Name": f"Thing{i}", "Superclass": "Instance",
                     "Tags": ["Deprecated", {"PreferredDescriptorName": "Thing0"}] if i == 5 else [],
                     "Members": [{"Name": "Fire", "MemberType": "Event", "Parameters": [
                         {"Name": "who", "Type": {"Category": "Class", "Name": "Player"}}],
                         "Security": "RobloxScriptSecurity"}]})
    enum_rows = [{"Name": f"E{i}", "Items": [{"Name": "A", "Value": 0, "Tags": ["Deprecated"]},
                                             {"Name": "B", "Value": 1, "LegacyNames": ["b"]}]} for i in range(enums)]
    return {"Version": 1, "Classes": rows, "Enums": enum_rows}


def test_compact_keeps_schema_and_meaning_but_drops_bulk():
    out = refresh.compact(_synthetic_dump())
    instance = out["Classes"][0]
    name, remove = instance["Members"]
    assert name == {"Name": "Name", "MemberType": "Property", "ValueType": {"Category": "Primitive", "Name": "string"}}
    assert remove["Tags"] == ["Deprecated"] and remove["PreferredDescriptorName"] == "Destroy"
    assert out["Classes"][6]["PreferredDescriptorName"] == "Thing0"
    assert out["Classes"][1]["Members"][0]["Security"] == "RobloxScriptSecurity"
    assert out["Enums"][0] == {"Name": "E0", "Items": [{"Name": "A", "Value": 0, "Tags": ["Deprecated"]},
                                                       {"Name": "B", "Value": 1}]}
    assert refresh.compact(out) == out  # idempotent on its own output


@pytest.mark.parametrize("mutate", [
    lambda d: d.pop("Classes"),
    lambda d: d.update(Version=2),
    lambda d: d["Classes"].append(dict(d["Classes"][1])),                       # duplicate class
    lambda d: d["Classes"][1].update(Superclass="Missing"),                     # unknown superclass
    lambda d: d["Classes"][1]["Members"].append({"Name": "x", "MemberType": "Gadget"}),
    lambda d: d["Enums"][0]["Items"].append({"Name": "C", "Value": "two"}),
    lambda d: d.update(Classes=d["Classes"][:10]),                              # truncated download
])
def test_compact_rejects_malformed_or_truncated_dumps(mutate):
    dump = _synthetic_dump()
    mutate(dump)
    with pytest.raises((ValueError, KeyError, TypeError)):
        refresh.compact(dump)


def test_build_render_and_main_are_deterministic_and_bounded(tmp_path, monkeypatch):
    raw = json.dumps(_synthetic_dump()).encode("utf-8")
    text = refresh.build(raw, studio_version="0.1.2.3", upload="version-0123456789abcdef", generated="2026-10-13")
    assert text == refresh.build(raw, studio_version="0.1.2.3", upload="version-0123456789abcdef",
                                 generated="2026-10-13")
    data = json.loads(text)
    assert data["StarSource"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert load_api_dump_from_text(tmp_path, text).classes["Thing3"].superclass == "Instance"
    source = tmp_path / "dump.json"
    source.write_bytes(raw)
    output = tmp_path / "out" / "roblox_api.json"
    assert refresh.main(["--input", str(source), "--version-upload", "version-0123456789abcdef",
                         "--studio-version", "0.1.2.3", "--output", str(output)]) == 0
    assert refresh.main(["--check", "--output", str(output)]) == 0
    output.write_text(output.read_text(encoding="utf-8").replace("\n", " ", 3), encoding="utf-8")
    assert refresh.main(["--check", "--output", str(output)]) == 1
    monkeypatch.setattr(refresh, "MAX_OUTPUT_BYTES", 100)
    with pytest.raises(ValueError, match="exceeds"):
        refresh.build(raw, studio_version="0.1.2.3", upload="version-0123456789abcdef", generated="2026-10-13")


def load_api_dump_from_text(tmp_path: Path, text: str):
    path = tmp_path / "check.json"
    path.write_text(text, encoding="utf-8")
    return load_api_dump(path)


def test_main_validates_offline_arguments(tmp_path):
    with pytest.raises(SystemExit):
        refresh.main(["--input", str(tmp_path / "x.json"), "--version-upload", "nope", "--studio-version", "1.2.3.4"])
    with pytest.raises(SystemExit):
        refresh.main(["--input", str(tmp_path / "x.json"), "--version-upload", "version-0123456789abcdef"])


@pytest.mark.parametrize("url", [
    "http://setup.rbxcdn.com/version-0123456789abcdef-Full-API-Dump.json",
    "https://example.com/dump.json",
    "https://setup.rbxcdn.com.evil.test/dump.json",
    "file:///etc/passwd",
])
def test_fetch_refuses_anything_but_https_to_the_official_hosts(url, monkeypatch):
    monkeypatch.setattr(refresh.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network used"))
    with pytest.raises(ValueError, match="refusing"):
        refresh._fetch(url)


def test_live_version_parsing_without_network(monkeypatch):
    monkeypatch.setattr(refresh, "_fetch", lambda url, limit=0: json.dumps(
        {"version": "0.742.0.7421053", "clientVersionUpload": "version-9b554450a0fc4e65"}).encode())
    assert refresh.live_studio_version() == ("0.742.0.7421053", "version-9b554450a0fc4e65")
    monkeypatch.setattr(refresh, "_fetch", lambda url, limit=0: b'{"version": "x", "clientVersionUpload": "y"}')
    with pytest.raises(ValueError):
        refresh.live_studio_version()


def test_fetch_caps_the_download_size(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, limit):
            return b"x" * limit

    monkeypatch.setattr(refresh.urllib.request, "urlopen", lambda *a, **k: Response())
    with pytest.raises(ValueError, match="larger"):
        refresh._fetch("https://setup.rbxcdn.com/version-0123456789abcdef-Full-API-Dump.json", limit=10)


# ---------------------------------------------------------------- cross-checks with other checkers

def test_lint_deprecation_tables_agree_with_the_dataset_when_present(dataset):
    rules = pytest.importorskip("star.luau_roblox_rules")
    for (service, method) in rules.DEPRECATED_SERVICE_METHODS:
        owner = "Workspace" if service == "Workspace" else service
        assert dataset.deprecation(owner, method) is not None, (service, method)
    for class_name in rules.DEPRECATED_CLASSES:
        assert dataset.deprecation(class_name) is not None, class_name
    for method in rules.DEPRECATED_INSTANCE_METHODS:
        assert dataset.deprecation("Instance", method) is not None, method
    for prop in rules.DEPRECATED_PROPERTIES:
        assert any(m.deprecated for m in dataset.find_member(prop)), prop


def test_skill_pack_examples_use_existing_non_deprecated_classes_and_services(dataset):
    packs = sorted((Path(api.__file__).parent / "skill_packs").glob("roblox-*/SKILL.md"))
    checked = 0
    for pack in packs:
        for example in re.findall(r"^~~~luau\n(.*?)\n~~~$", pack.read_text(encoding="utf-8"), re.M | re.S):
            for service in re.findall(r'GetService\("(\w+)"\)', example):
                assert service in dataset.services, (pack.parent.name, service)
                checked += 1
            for class_name in re.findall(r'Instance\.new\("(\w+)"\)', example):
                assert class_name in dataset.classes and dataset.deprecation(class_name) is None, (
                    pack.parent.name, class_name)
                checked += 1
            for enum, item in re.findall(r"\bEnum\.(\w+)\.(\w+)", example):
                assert item in dataset.enums.get(enum, ()), (pack.parent.name, enum, item)
                checked += 1
    assert checked > 20
