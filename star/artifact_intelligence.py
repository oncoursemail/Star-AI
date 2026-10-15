"""Read-only glTF/GLB structure and game-asset quality evidence for STAR.

No renderer, decompiler, downloaded validator, external URI loader or executable.
This is a fast first-pass structural audit, NOT conformance certification or proof
of animation/visual quality. For full validation use Khronos glTF-Validator and
review the asset in its destination engine.
"""
from __future__ import annotations

import json
from pathlib import Path
import struct

MAX_JSON_BYTES = 2_000_000
MAX_ASSET_BYTES = 64_000_000
MAX_ENTRIES = 4096
MAX_MESSAGES = 32
FORMATS = frozenset({".gltf", ".glb"})
TARGETS = frozenset({"general", "roblox", "godot", "unity", "unreal"})
SOURCE = "https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html"


def _parse_json(raw: bytes) -> dict:
    try:
        value = json.loads(raw.decode("utf-8").rstrip(" \t\r\n\x00"),
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError("Invalid glTF JSON document") from exc
    if not isinstance(value, dict):
        raise ValueError("glTF document must be an object")
    return value


def _load(path: Path) -> tuple[dict, str]:
    """Read only the GLB JSON chunk. Geometry buffers are never loaded or executed."""
    size = path.stat().st_size
    if not 0 < size <= MAX_ASSET_BYTES:
        raise ValueError("Asset exceeds the 64 MB read-only audit limit")
    with path.open("rb") as source:
        if path.suffix.lower() == ".gltf":
            if size > MAX_JSON_BYTES:
                raise ValueError("glTF JSON exceeds the 2 MB audit limit")
            return _parse_json(source.read(MAX_JSON_BYTES + 1)), "gltf"
        if path.suffix.lower() != ".glb":
            raise ValueError("Only .gltf and .glb assets can be audited")
        header = source.read(20)
        if len(header) != 20:
            raise ValueError("Truncated GLB header")
        magic, version, declared_size, chunk_size, chunk_type = struct.unpack("<4sIII4s", header)
        if magic != b"glTF" or version != 2 or declared_size != size:
            raise ValueError("Invalid GLB magic, version or file length")
        if chunk_type != b"JSON" or chunk_size % 4 != 0 or chunk_size > MAX_JSON_BYTES:
            raise ValueError("Invalid or oversized GLB JSON chunk")
        if 20 + chunk_size > size:
            raise ValueError("GLB JSON chunk runs beyond the file")
        return _parse_json(source.read(chunk_size)), "glb"


def audit(workspace, path: str, *, target: str = "general", triangle_budget: int = 100_000) -> dict:
    """Inspect one explicitly selected workspace asset; do not follow external URIs."""
    if target not in TARGETS:
        raise ValueError("Unknown destination engine")
    if type(triangle_budget) is not int or not 1_000 <= triangle_budget <= 10_000_000:
        raise ValueError("Triangle budget must be an integer in 1,000..10,000,000")
    location = workspace.resolve(path)
    if location.is_symlink() or not location.is_file() or location.suffix.lower() not in FORMATS:
        raise ValueError("Select a regular .gltf or .glb workspace file")
    data, encoding = _load(location)
    errors: list[str] = []
    warnings: list[str] = []

    def error(message: str) -> None:
        if len(errors) < MAX_MESSAGES:
            errors.append(message)

    def warn(message: str) -> None:
        if len(warnings) < MAX_MESSAGES:
            warnings.append(message)

    def entries(key: str) -> list:
        value = data.get(key, [])
        if not isinstance(value, list) or len(value) > MAX_ENTRIES:
            error(f"{key} must be a bounded array")
            return []
        return value

    arrays = {key: entries(key) for key in (
        "nodes", "meshes", "scenes", "skins", "animations", "accessors",
        "materials", "textures", "images", "buffers", "bufferViews"
    )}
    nodes, meshes = arrays["nodes"], arrays["meshes"]
    accessors = arrays["accessors"]

    def index(value, key: str, label: str) -> bool:
        if type(value) is not int or not 0 <= value < len(arrays[key]):
            error(f"{label}: invalid {key} index")
            return False
        return True

    asset = data.get("asset")
    if not isinstance(asset, dict) or asset.get("version") != "2.0":
        error("Not a supported glTF 2.0 asset")
    for key, value in arrays.items():
        if any(not isinstance(item, dict) for item in value):
            error(f"{key}: entries must be objects")

    # glTF node hierarchy is a directed acyclic forest, not a general graph.
    children_by_node: list[list[int]] = []
    parents = [0] * len(nodes)
    instance_meshes: list[int] = []
    for node_id, node in enumerate(nodes):
        if not isinstance(node, dict):
            children_by_node.append([])
            continue
        valid_children = []
        children = node.get("children", [])
        if not isinstance(children, list) or len(children) > MAX_ENTRIES:
            error(f"node {node_id}: invalid children array")
            children = []
        for child in children:
            if index(child, "nodes", f"node {node_id} child"):
                valid_children.append(child)
                parents[child] += 1
        children_by_node.append(valid_children)
        if "mesh" in node and index(node["mesh"], "meshes", f"node {node_id} mesh"):
            instance_meshes.append(node["mesh"])
        if "skin" in node:
            index(node["skin"], "skins", f"node {node_id} skin")
            if "mesh" not in node:
                warn(f"node {node_id}: skin without mesh")
    if any(count > 1 for count in parents):
        error("Node hierarchy shares a child across multiple parents")
    state = [0] * len(nodes)
    for start in range(len(nodes)):
        if state[start]:
            continue
        state[start] = 1
        stack = [(start, iter(children_by_node[start]))]
        while stack:
            vertex, edges = stack[-1]
            try:
                child = next(edges)
            except StopIteration:
                state[vertex] = 2
                stack.pop()
                continue
            if state[child] == 1:
                error("Node hierarchy contains a cycle")
                break
            if state[child] == 0:
                state[child] = 1
                stack.append((child, iter(children_by_node[child])))
        # Mark remaining nodes visited before continuing after a cycle.
        for vertex, _ in stack:
            state[vertex] = 2
    for scene_id, scene in enumerate(arrays["scenes"]):
        if isinstance(scene, dict):
            roots = scene.get("nodes", [])
            if not isinstance(roots, list) or len(roots) > MAX_ENTRIES:
                error(f"scene {scene_id}: invalid root nodes array")
                continue
            for node in roots:
                index(node, "nodes", f"scene {scene_id} root")
    if "scene" in data:
        index(data["scene"], "scenes", "default scene")

    for accessor_id, accessor in enumerate(accessors):
        if not isinstance(accessor, dict):
            continue
        count = accessor.get("count")
        if type(count) is not int or not 0 <= count <= 50_000_000:
            error(f"accessor {accessor_id}: invalid count")
        if "bufferView" in accessor:
            index(accessor["bufferView"], "bufferViews", f"accessor {accessor_id}")
    mesh_triangles = []
    missing_normals = 0
    missing_uvs = 0
    skinned_primitives = 0
    for mesh_id, mesh in enumerate(meshes):
        if not isinstance(mesh, dict):
            mesh_triangles.append(0)
            continue
        primitives = mesh.get("primitives", [])
        if not isinstance(primitives, list) or len(primitives) > MAX_ENTRIES:
            error(f"mesh {mesh_id}: invalid primitives array")
            primitives = []
        triangle_total = 0
        for primitive_id, primitive in enumerate(primitives):
            if not isinstance(primitive, dict):
                error(f"mesh {mesh_id}: invalid primitive")
                continue
            label = f"mesh {mesh_id} primitive {primitive_id}"
            attributes = primitive.get("attributes")
            if not isinstance(attributes, dict) or "POSITION" not in attributes:
                error(f"{label}: missing POSITION")
                continue
            for semantic, accessor_id in attributes.items():
                index(accessor_id, "accessors", f"{label} {str(semantic)[:32]}")
            position_id = attributes["POSITION"]
            if not index(position_id, "accessors", f"{label} POSITION"):
                continue
            position = accessors[position_id]
            if not isinstance(position, dict):
                continue
            if position.get("type") != "VEC3":
                error(f"{label}: POSITION must be VEC3")
            if "min" not in position or "max" not in position:
                warn(f"{label}: POSITION bounds missing")
            if "NORMAL" not in attributes:
                missing_normals += 1
            if "TEXCOORD_0" not in attributes:
                missing_uvs += 1
            if "JOINTS_0" in attributes or "WEIGHTS_0" in attributes:
                skinned_primitives += 1
                if ("JOINTS_0" in attributes) != ("WEIGHTS_0" in attributes):
                    error(f"{label}: incomplete skin joint/weight pair")
            if "material" in primitive:
                index(primitive["material"], "materials", f"{label} material")
            count = position.get("count", 0)
            if "indices" in primitive and index(primitive["indices"], "accessors", f"{label} indices"):
                source_accessor = accessors[primitive["indices"]]
                if isinstance(source_accessor, dict):
                    count = source_accessor.get("count", 0)
                    if source_accessor.get("type") != "SCALAR":
                        error(f"{label}: index accessor must be SCALAR")
            if type(count) is not int or not 0 <= count <= 50_000_000:
                continue
            mode = primitive.get("mode", 4)
            if type(mode) is not int or not 0 <= mode <= 6:
                error(f"{label}: invalid topology mode")
            elif mode == 4:
                triangle_total += count // 3
                if count % 3:
                    warn(f"{label}: triangle-list element count not divisible by three")
            elif mode in (5, 6):
                triangle_total += max(count - 2, 0)
        mesh_triangles.append(triangle_total)

    joints_count = 0
    for skin_id, skin in enumerate(arrays["skins"]):
        if not isinstance(skin, dict):
            continue
        joints = skin.get("joints")
        if not isinstance(joints, list) or not joints or len(joints) > MAX_ENTRIES:
            error(f"skin {skin_id}: invalid joints")
            continue
        joints_count += len(joints)
        for joint in joints:
            index(joint, "nodes", f"skin {skin_id} joint")
        if "inverseBindMatrices" in skin and index(
            skin["inverseBindMatrices"], "accessors", f"skin {skin_id} inverse bind"
        ):
            accessor = accessors[skin["inverseBindMatrices"]]
            if isinstance(accessor, dict) and accessor.get("count") != len(joints):
                error(f"skin {skin_id}: inverse bind matrix count differs from joints")
    clip_summaries = []
    for clip_id, clip in enumerate(arrays["animations"]):
        if not isinstance(clip, dict):
            continue
        samplers = clip.get("samplers", [])
        channels = clip.get("channels", [])
        if not isinstance(samplers, list) or not isinstance(channels, list) or (
            len(samplers) > MAX_ENTRIES or len(channels) > MAX_ENTRIES
        ):
            error(f"animation {clip_id}: invalid channels or samplers")
            continue
        for sampler_id, sampler in enumerate(samplers):
            if isinstance(sampler, dict):
                index(sampler.get("input"), "accessors", f"animation {clip_id} sampler {sampler_id} input")
                index(sampler.get("output"), "accessors", f"animation {clip_id} sampler {sampler_id} output")
            else:
                error(f"animation {clip_id}: invalid sampler")
        for channel in channels:
            if not isinstance(channel, dict):
                error(f"animation {clip_id}: invalid channel")
                continue
            sampler_id = channel.get("sampler")
            if type(sampler_id) is not int or not 0 <= sampler_id < len(samplers):
                error(f"animation {clip_id}: invalid sampler index")
            target_node = channel.get("target", {})
            if not isinstance(target_node, dict) or (
                "node" in target_node and not index(target_node["node"], "nodes", f"animation {clip_id} target")
            ):
                error(f"animation {clip_id}: invalid target")
        clip_summaries.append({
            "name": str(clip.get("name", f"clip_{clip_id}"))[:64],
            "channels": len(channels),
        })
    triangle_count = sum(mesh_triangles[i] for i in instance_meshes)
    if not instance_meshes:
        triangle_count = sum(mesh_triangles)
        if meshes:
            warn("No mesh instances found; triangle count is for uninstanced definitions")
    if triangle_count > triangle_budget:
        warn(f"Estimated triangles {triangle_count} exceed the selected budget {triangle_budget}")
    if missing_normals:
        warn(f"{missing_normals} primitives lack vertex normals; review shading")
    if missing_uvs:
        warn(f"{missing_uvs} primitives lack TEXCOORD_0; inspect texture mapping")
    if joints_count and not skinned_primitives:
        warn("Skeletons exist but no mesh primitive has joint/weight attributes")
    if not arrays["animations"]:
        warn("No authored animation clips found")
    if not arrays["materials"]:
        warn("No explicit PBR materials found")
    external_resources = 0
    for key in ("images", "buffers"):
        for item in arrays[key]:
            if isinstance(item, dict) and isinstance(item.get("uri"), str):
                external_resources += 1
    if external_resources:
        warn(f"{external_resources} referenced resources were not opened or validated")
    if data.get("extensionsRequired"):
        warn("Required glTF extensions need a compatible destination engine")
    result = {
        "path": location.relative_to(workspace.root).as_posix(),
        "format": encoding, "target": target, "read_only": True,
        "structural_issues": errors, "quality_warnings": warnings,
        "structure_checked": len(errors) == 0,
        "statistics": {
            "mesh_definitions": len(meshes), "mesh_instances": len(instance_meshes),
            "triangles_estimated": triangle_count, "triangle_budget": triangle_budget,
            "materials": len(arrays["materials"]), "textures": len(arrays["textures"]),
            "skins": len(arrays["skins"]), "joint_references": joints_count,
            "animations": clip_summaries, "external_resources_unverified": external_resources,
        },
        "specification": SOURCE,
        "notice": ("Preliminary static inspection only. No geometry buffers, rendered images, "
                   "skin weights, collision, clip playback, import or licensing were validated. "
                   "Use Khronos glTF-Validator, then preview and test in the destination engine."),
    }
    return result
