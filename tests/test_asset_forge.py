"""Offline asset research, architecture and world sampling contract tests."""
import httpx
import pytest

from star.asset_forge import PolyHavenCatalog, plan_building, preview_terrain, terrain_height


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False, trust_env=False)


def test_polyhaven_uses_only_fixed_read_only_endpoints_and_source_metadata():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        assert request.method == "GET"
        assert request.url.host == "api.polyhaven.com"
        if request.url.path == "/search":
            assert request.url.params.get("q") == "mossy stone"
            assert request.url.params.get("t") == "models"
            assert request.url.params.get("future") == "false"
            return httpx.Response(200, json={"results": [
                {"slug": "mossy_rock", "score": .82},
                {"slug": "../../../../secrets", "score": 1},
            ]})
        assert request.url.path == "/info/mossy_rock"
        return httpx.Response(200, json={"type": 2, "name": "Mossy Rock", "description": "Mossy environment prop",
                                          "date_published": 1660000000, "category": "Rocks",
                                          "thumbnail_url": "https://cdn.polyhaven.com/asset_img/thumbs/mossy_rock.png"})

    with PolyHavenCatalog(client=client(handler), now=lambda: 2000000000) as catalog:
        result = catalog.search("  MOSSY STONE  ", kind="models", limit=4)
    assert len(calls) == 2
    assert result["credit"] == "Powered by Poly Haven" and result["untrusted"] is True
    assert result["assets"][0]["license"] == "CC0"
    assert result["assets"][0]["source_url"] == "https://polyhaven.com/a/mossy_rock"
    assert len(result["assets"]) == 1


@pytest.mark.parametrize("kwargs", [
    {"query": ""}, {"query": "q" * 101}, {"query": 7},
    {"query": "stone", "kind": "gltf"}, {"query": "stone", "limit": 0},
    {"query": "stone", "limit": True}, {"query": "stone", "limit": 10},
])
def test_invalid_asset_requests_never_touch_network(kwargs):
    def handler(_):
        pytest.fail("invalid request made a network call")
    with PolyHavenCatalog(client=client(handler)) as catalog:
        with pytest.raises(ValueError):
            catalog.search(**kwargs)


@pytest.mark.parametrize("code", [302, 429, 503])
def test_api_redirect_or_failure_never_leaks_to_other_hosts(code):
    calls = []
    def handler(request):
        calls.append(request.url.host)
        return httpx.Response(code, headers={"location": "https://evil.example/steal"})
    with PolyHavenCatalog(client=client(handler)) as catalog:
        with pytest.raises(ValueError, match=f"HTTP {code}"):
            catalog.search("rock")
    assert calls == ["api.polyhaven.com"]


def test_invalid_info_type_future_asset_and_untrusted_thumbnail_are_rejected():
    def handler(request):
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [{"slug": "early_rock"}, {"slug": "wood_floor"}]})
        if request.url.path == "/info/early_rock":
            return httpx.Response(200, json={"type": 2, "date_published": 2100000000})
        return httpx.Response(200, json={"type": 2, "name": "Wood floor", "thumbnail_url": "https://evil.example/p.png"})
    with PolyHavenCatalog(client=client(handler), now=lambda: 2000000000) as catalog:
        result = catalog.search("floor")
    assert [r["id"] for r in result["assets"]] == ["wood_floor"]
    assert result["assets"][0]["thumbnail_url"] is None


def test_bounded_response_and_malformed_search_fail_closed():
    for response in (httpx.Response(200, content=b"x" * 170000),
                     httpx.Response(200, json={"results": "not-a-list"})):
        with PolyHavenCatalog(client=client(lambda _: response)) as catalog:
            with pytest.raises(ValueError):
                catalog.search("pine")


def test_modular_architecture_entrance_stairs_cutouts_and_repeatability():
    a = plan_building(width_bays=5, depth_bays=4, floors=3, style="classic-studs", seed=23)
    assert a == plan_building(width_bays=5, depth_bays=4, floors=3, style="classic-studs", seed=23)
    assert a["stage"] == "plan_only"
    assert a["footprint_studs"] == [60, 48]
    doors = [m for m in a["modules"] if m.get("opening") == "door"]
    assert len(doors) == 1 and doors[0]["id"] == "wall-front-0-2"
    assert len([m for m in a["modules"] if m["kind"] == "stairs"]) == 2
    slabs = [m for m in a["modules"] if m["kind"] == "floor-slab"]
    assert slabs[0]["cutouts"] == []
    assert slabs[1]["cutouts"] == slabs[2]["cutouts"] == [{"bay": [1, 2], "kind": "stairwell"}]
    assert all(len(m["size"]) == 3 for m in a["modules"] if "size" in m)
    assert all(zone["purpose"] in ("stairs", "landing", "room", "corridor") for zone in a["zones"])


@pytest.mark.parametrize("kwargs", [
    {"width_bays": 2}, {"depth_bays": 7}, {"floors": 4}, {"seed": -1},
    {"style": "unknown"}, {"floors": False},
])
def test_architecture_rejects_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        plan_building(**kwargs)


def test_terrain_world_coordinates_are_seam_stable_and_deterministic():
    first = preview_terrain(seed=71, biome="alien", size=4, origin_x=0, origin_z=0, step=16)
    adjoining = preview_terrain(seed=71, biome="alien", size=4, origin_x=48, origin_z=0, step=16)
    assert [row[-1] for row in first["heights_studs"]] == [row[0] for row in adjoining["heights_studs"]]
    assert first == preview_terrain(seed=71, biome="alien", size=4)
    assert first != preview_terrain(seed=72, biome="alien", size=4)
    assert first["stage"] == "heightmap_preview"


@pytest.mark.parametrize("biome", ["temperate", "desert", "alien", "alpine"])
def test_terrain_biomes_are_nonnegative_and_finite(biome):
    result = preview_terrain(seed=5, biome=biome, size=8)
    assert all(0 <= height < 200 and height == height
               for row in result["heights_studs"] for height in row)
    assert terrain_height(0, 0, seed=5, biome=biome) >= 0


@pytest.mark.parametrize("kwargs", [
    {"biome": "forest-of-urls"}, {"size": 17}, {"size": 1},
    {"origin_x": 1000000}, {"step": 0}, {"seed": True},
])
def test_terrain_rejects_unsafe_or_unbounded_requests(kwargs):
    with pytest.raises(ValueError):
        preview_terrain(**kwargs)
