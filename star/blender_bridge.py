"""STAR's local Blender worker controller: bounded 3D scene jobs, never model Python.

Blender is an optional user-installed program. Only the trusted bundled worker is run
in a fresh factory-startup process. Jobs live in per-project, non-overwriting folders.
No external Blender MCP addon, network listener, downloaded scripts or assets are used.
"""
from __future__ import annotations

from functools import lru_cache
import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import shutil

from ._lazy import lazy_attr
Draft202012Validator = lazy_attr("jsonschema", "Draft202012Validator")  # loaded on first validation

SCENE_NAME = r"^[A-Za-z][A-Za-z0-9_-]{1,39}$"
HEX = r"^#[0-9a-fA-F]{6}$"
VECTOR = {"type": "array", "items": {"type": "number", "minimum": -200, "maximum": 200},
          "minItems": 3, "maxItems": 3}
SCALE = {"type": "array", "items": {"type": "number", "exclusiveMinimum": 0, "maximum": 40},
         "minItems": 3, "maxItems": 3}
OBJECT = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "pattern": SCENE_NAME},
        "kind": {"type": "string", "enum": ["cube", "cylinder", "cone", "sphere", "rock", "tree", "arch", "roof"]},
        "location": VECTOR, "scale": SCALE,
        "rotation": {"type": "array", "items": {"type": "number", "minimum": -360, "maximum": 360},
                     "minItems": 3, "maxItems": 3},
        "color": {"type": "string", "pattern": HEX},
    },
    "required": ["name", "kind", "location", "scale"],
}
CAMERA = {"type": "object", "additionalProperties": False,
          "properties": {"location": VECTOR, "target": VECTOR},
          "required": ["location", "target"]}
SCENE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "pattern": SCENE_NAME},
        "objects": {"type": "array", "minItems": 1, "maxItems": 48, "items": OBJECT},
        "camera": CAMERA,
        "render_preview": {"type": "boolean"},
        "sky_color": {"type": "string", "pattern": HEX},
        "ground_color": {"type": "string", "pattern": HEX},
    },
    "required": ["name", "objects"],
}


@lru_cache(maxsize=1)
def _validator():
    """The scene schema validator, built on first use (jsonschema is not imported at start-up)."""
    return Draft202012Validator(SCENE_SCHEMA)


JOB_ID = re.compile(r"^[a-f0-9]{24}$")
MAX_SPEC_BYTES = 24_000
MAX_REPORT_BYTES = 80_000
MAX_JOB_SECONDS = 180


class BlenderUnavailable(RuntimeError):
    pass


class BlenderJobError(RuntimeError):
    pass


def validate_scene(spec: object) -> dict:
    """Strict, small, JSON-only operation grammar; never take arbitrary bpy code."""
    if type(spec) is not dict:
        raise ValueError("Blender scene must be a JSON object")
    try:
        encoded = json.dumps(spec, allow_nan=False, ensure_ascii=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Blender scene contains invalid JSON values") from exc
    if len(encoded.encode("utf-8")) > MAX_SPEC_BYTES:
        raise ValueError("Blender scene request is too large")
    errors = list(_validator().iter_errors(spec))
    if errors:
        raise ValueError("Unsupported Blender scene field or out-of-range value")
    names = [item["name"].casefold() for item in spec["objects"]]
    if len(set(names)) != len(names):
        raise ValueError("Blender scene object names must be unique")
    camera = spec.get("camera")
    if camera is not None and camera["location"] == camera["target"]:
        raise ValueError("Blender camera must not point at its own location")
    # Roundtrip makes the worker input immutable to later mutation by the caller.
    return json.loads(encoded)


def _allowed_executable(path: Path) -> bool:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        return False
    if os.name == "nt":
        return path.suffix.lower() == ".exe" and not str(path).startswith("\\\\")
    return os.access(path, os.X_OK)


def discover_blender(configured: str = "") -> Path | None:
    """Local-only detection. Does not run Blender or install anything."""
    if configured:
        if (not isinstance(configured, str) or len(configured) > 2048
                or "\x00" in configured or configured.startswith(("\\\\", "//"))
                or "://" in configured):
            return None
        path = Path(configured).expanduser()
        return path.resolve() if _allowed_executable(path) else None
    on_path = shutil.which("blender")
    if on_path:
        path = Path(on_path)
        if _allowed_executable(path):
            return path.resolve()
    if os.name == "nt":
        roots = (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramW6432", ""))
        for root in roots:
            if not root:
                continue
            parent = Path(root) / "Blender Foundation"
            if parent.is_dir():
                for path in sorted(parent.glob("Blender */blender.exe"), reverse=True):
                    if _allowed_executable(path):
                        return path.resolve()
    return None


def _job_root(home: Path, project: str) -> Path:
    """Slug and hash project identity; reject a symlink escaping STAR's data."""
    safe_name = re.sub(r"[^a-z0-9_-]", "-", project.casefold()).strip("-")[:32] or "project"
    short_hash = sha256(project.encode("utf-8")).hexdigest()[:10]
    root = home.resolve()
    jobs = root / "blender" / "jobs" / (safe_name + "-" + short_hash)
    # Reject a pre-planted symlink in any ancestor; the profile itself may be a symlink.
    for candidate in (root / "blender", root / "blender" / "jobs", jobs):
        if candidate.is_symlink():
            raise PermissionError("Blender project storage must not be a symlink")
    if not jobs.resolve().is_relative_to(root):
        raise PermissionError("Blender job would leave STAR's profile")
    return jobs


def _worker_environment() -> dict:
    """Do not give Blender the owner's model/cloud keys or Roblox credentials."""
    allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR",
               "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "LANG",
               "LC_ALL", "DISPLAY", "XDG_RUNTIME_DIR", "XDG_CONFIG_HOME")
    return {key: os.environ[key] for key in allowed if key in os.environ}


def status(settings) -> dict:
    enabled = getattr(settings, "blender_enabled", False) is True
    editable = enabled and getattr(settings, "blender_edit", False) is True
    configured = getattr(settings, "blender_executable", "")
    executable = discover_blender(configured)
    return {
        "enabled": enabled, "installed": executable is not None,
        "edit_enabled": editable, "executable": str(executable) if executable else "",
        "connection": "local-stdio-mcp", "ready": enabled and executable is not None,
        "note": ("Blender available locally; verify by testing before a build."
                 if executable else "Install Blender locally or choose its executable. No automatic download."),
    }


class BlenderController:
    """Trusted host for one project, not a general file-process execution service."""

    def __init__(self, *, settings, home: Path, spawn=None):
        self.settings = settings
        self.home = Path(home)
        self.spawn = spawn or asyncio.create_subprocess_exec
        self.serial = asyncio.Lock()

    def _executable(self) -> Path:
        if getattr(self.settings, "blender_enabled", False) is not True:
            raise PermissionError("Enable Blender in STAR settings first")
        path = discover_blender(getattr(self.settings, "blender_executable", ""))
        if path is None:
            raise BlenderUnavailable("Blender is not installed or the configured executable is unavailable")
        return path

    async def _invoke(self, *args: str, cwd: Path | None = None, timeout: int = 25) -> tuple[int, bytes, bytes]:
        proc = await self.spawn(*args, cwd=str(cwd) if cwd else None, env=_worker_environment(),
                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            output, errors = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode, output[:120_000], errors[:120_000]
        except BaseException:
            if proc.returncode is None:
                proc.kill()
                await proc.communicate()
            raise

    async def probe(self) -> dict:
        executable = self._executable()
        expr = 'import bpy; print("STAR_BLENDER_VERSION="+bpy.app.version_string)'
        async with self.serial:
            try:
                code, output, _ = await self._invoke(str(executable), "--background",
                    "--factory-startup", "--python-exit-code", "17", "--python-expr", expr, timeout=25)
            except (OSError, asyncio.TimeoutError) as exc:
                raise BlenderUnavailable("Blender was not able to start") from exc
        match = re.search(rb"STAR_BLENDER_VERSION=([0-9][0-9A-Za-z. ]{0,45})", output)
        if code or not match:
            raise BlenderUnavailable("Blender version probe failed")
        return {"ready": True, "version": match.group(1).decode("ascii").strip(),
                "executable": str(executable), "tested": True}

    def inspect(self, job_id: str) -> dict:
        if getattr(self.settings, "blender_enabled", False) is not True:
            raise PermissionError("Enable Blender in STAR settings before inspecting its jobs")
        if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
            raise ValueError("Unknown Blender job identifier")
        root = _job_root(self.home, self.settings.project)
        directory = root / job_id
        if directory.is_symlink():
            raise PermissionError("Blender job directory cannot be a symlink")
        manifest = directory / "result.json"
        if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > MAX_REPORT_BYTES:
            raise ValueError("Job report not found or invalid")
        report = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(report, dict) or report.get("job_id") != job_id or report.get("status") != "completed":
            raise ValueError("Blender job report did not pass validation")
        # Never trust arbitrary paths reported by a worker. Animation jobs are
        # separate draft artifacts, with FBX not GLB, and no claimed Studio proof.
        if report.get("kind") == "animation":
            for name in ("scene.blend", "animation.fbx"):
                file = directory / name
                if file.is_symlink() or not file.is_file() or not 0 < file.stat().st_size <= 150_000_000:
                    raise ValueError("Expected Blender animation draft is missing or too large")
            if report.get("rig") != "r15" or report.get("native_studio_import_tested") is not False:
                raise ValueError("Blender animation evidence is invalid")
            return {"job_id": job_id, "scene": report.get("scene"), "kind": "animation",
                    "rig": "r15", "fps": report.get("fps"),
                    "frame_count": report.get("frame_count"),
                    "keyed_joints": report.get("keyed_joints"),
                    "blend_file": str(directory / "scene.blend"),
                    "fbx_file": str(directory / "animation.fbx"),
                    "preview_file": None, "native_studio_import_tested": False,
                    "notice": ("Experimental BONE-ONLY R15 proxy FBX. Must import to and test in "
                               "real target Roblox rig using Studio Animation Editor. Not R6 compatible.")}
        for name in ("scene.blend", "scene.glb"):
            file = directory / name
            if file.is_symlink() or not file.is_file() or file.stat().st_size == 0:
                raise ValueError("Expected Blender output is missing")
        return {"job_id": job_id, "scene": report.get("scene"), "objects": report.get("objects"),
                "mesh_count": report.get("mesh_count"), "triangle_count": report.get("triangle_count"),
                "blend_file": str(directory / "scene.blend"), "glb_file": str(directory / "scene.glb"),
                "preview_file": str(directory / "preview.png") if (
                    (directory / "preview.png").is_file() and not (directory / "preview.png").is_symlink()) else None,
                "notice": "Export files exist; Studio import, visual similarity and rig behavior are not verified."}

    async def build(self, spec: dict) -> dict:
        if getattr(self.settings, "blender_edit", False) is not True:
            raise PermissionError("Allow Blender scene creation explicitly in STAR settings")
        scene = validate_scene(spec)
        executable = self._executable()
        worker = Path(__file__).with_name("blender_worker.py")
        if not worker.is_file():
            raise BlenderUnavailable("STAR's bundled Blender worker is missing")
        # Serialized jobs avoid racing within this Brain 2 session. Every job is immutable.
        async with self.serial:
            root = _job_root(self.home, self.settings.project)
            root.mkdir(parents=True, exist_ok=True)
            job_id = secrets.token_hex(12)
            directory = root / job_id
            directory.mkdir(mode=0o700, exist_ok=False)
            (directory / "scene.json").write_text(json.dumps(scene, sort_keys=True), encoding="utf-8")
            from .discord_bot.native_evidence import emit
            emit("blender-worker", {"job_id": job_id, "status": "running"}, directory, scene=scene)
            try:
                code, out, err = await self._invoke(str(executable), "--background",
                    "--factory-startup", "--python-exit-code", "17", "--python", str(worker),
                    "--", str(directory / "scene.json"), cwd=directory, timeout=MAX_JOB_SECONDS)
            except asyncio.TimeoutError as exc:
                raise BlenderJobError("Blender worker exceeded its execution time limit; inspect local job logs") from exc
            except OSError as exc:
                raise BlenderUnavailable("Blender executable could not start") from exc
            (directory / "worker.log").write_bytes((out + b"\n" + err)[-40_000:])
            if code:
                raise BlenderJobError("Blender scene job failed; inspect the job's private worker.log")
            report = self.inspect(job_id)
            emit("blender-worker", report, directory, scene=scene)
            return report



    async def animate(self, spec: dict) -> dict:
        """Generate one R15 bone-only FBX draft in a new project-private job.

        Distinct experimental opt-in on top of the existing Blender create
        permission. Refuses R6 until a verified Motor6D Studio import path is
        available. Never imports user-owned assets or invokes arbitrary bpy.
        """
        from .blender_animation import validate_animation

        if getattr(self.settings, "blender_edit", False) is not True:
            raise PermissionError("Allow Blender scene creation explicitly in STAR settings")
        if os.environ.get("STAR_BLENDER_R15_ANIMATION_EXPERIMENT") != "on":
            raise PermissionError("R15 animation export is experimental and off by default")
        clip = validate_animation(spec)
        if clip["rig"] != "r15":
            raise ValueError("R6 requires native Motor6D retarget testing; use animation preflight only")
        executable = self._executable()
        worker = Path(__file__).with_name("blender_animation_worker.py")
        if not worker.is_file() or worker.is_symlink():
            raise BlenderUnavailable("STAR's trusted animation worker is not available")
        async with self.serial:
            root = _job_root(self.home, self.settings.project)
            root.mkdir(parents=True, exist_ok=True)
            job_id = secrets.token_hex(12)
            directory = root / job_id
            directory.mkdir(mode=0o700, exist_ok=False)
            (directory / "animation.json").write_text(
                json.dumps(clip, sort_keys=True), encoding="utf-8")
            try:
                code, out, err = await self._invoke(
                    str(executable), "--background", "--factory-startup",
                    "--python-exit-code", "17", "--python", str(worker),
                    "--", str(directory / "animation.json"),
                    cwd=directory, timeout=MAX_JOB_SECONDS)
            except asyncio.TimeoutError as exc:
                raise BlenderJobError("Blender animation exceeded its bounded time budget") from exc
            except OSError as exc:
                raise BlenderUnavailable("Blender executable could not start") from exc
            (directory / "worker.log").write_bytes((out + b"\n" + err)[-40_000:])
            if code:
                raise BlenderJobError(
                    "Blender R15 draft animation failed; inspect its private worker.log")
            return self.inspect(job_id)


def main(argv: list[str] | None = None) -> int:
    """Owner-run smoke checks, independent of LLM inference or an MCP client."""
    import argparse
    from .desktop_core import Settings

    parser = argparse.ArgumentParser(description="STAR's guarded local Blender scene workflow")
    parser.add_argument("--settings", type=Path, required=True, help="An existing STAR settings JSON")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--probe", action="store_true")
    actions.add_argument("--scene", type=Path, help="Owner-reviewed JSON scene recipe")
    actions.add_argument("--preflight-animation", type=Path, help="Read-only R15 or R6 animation check")
    actions.add_argument("--animation", type=Path, help="Experimental approved R15 FBX draft export")
    actions.add_argument("--inspect", type=str, help="Previous STAR Blender job ID")
    arguments = parser.parse_args(argv)
    if not arguments.settings.is_file():
        parser.error("STAR settings JSON not found")
    settings = Settings.load(arguments.settings)
    settings.validate()
    controller = BlenderController(settings=settings, home=arguments.settings.parent)
    try:
        if arguments.probe:
            report = asyncio.run(controller.probe())
        elif arguments.scene:
            file = arguments.scene
            if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_SPEC_BYTES:
                raise ValueError("Choose a regular small local JSON scene file")
            spec = validate_scene(json.loads(file.read_text(encoding="utf-8")))
            report = asyncio.run(controller.build(spec))
        elif arguments.preflight_animation or arguments.animation:
            from .blender_animation import analyze_animation, validate_animation

            file = arguments.preflight_animation or arguments.animation
            if (file.is_symlink() or not file.is_file() or
                    not 0 < file.stat().st_size <= MAX_SPEC_BYTES):
                raise ValueError("Choose a regular small local JSON animation recipe")
            spec = validate_animation(json.loads(file.read_text(encoding="utf-8")))
            if arguments.preflight_animation:
                report = analyze_animation(spec)
            else:
                report = asyncio.run(controller.animate(spec))
        else:
            report = controller.inspect(arguments.inspect)
    except (ValueError, PermissionError, BlenderUnavailable, BlenderJobError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
