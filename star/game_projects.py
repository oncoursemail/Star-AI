"""Bounded, read-only game-engine project discovery and command previews.

No engine is launched here. A command preview is untrusted project context, not
an authorization to run code or publish a build.
"""
from __future__ import annotations

import json
import re
from itertools import islice
from pathlib import Path

# Keep scans bounded even when a workspace contains generated assets or huge vendor trees.
MAX_SCAN_ENTRIES = 1200
MAX_PROJECTS = 12
MAX_MANIFEST_BYTES = 64_000
SKIP_DIRS = frozenset({
    '.git', '.github', '.godot', '.idea', '.vs', '.vscode', 'Library', 'Temp', 'Logs',
    'Obj', 'Build', 'Builds', 'Binaries', 'DerivedDataCache', 'Intermediate',
    'Saved', 'node_modules', 'venv', '.venv', '__pycache__', 'dist',
})
LANGUAGES = {
    '.gd': 'GDScript', '.cs': 'C#', '.cpp': 'C++', '.cc': 'C++', '.c': 'C',
    '.h': 'C/C++ headers', '.hpp': 'C/C++ headers', '.lua': 'Lua',
    '.luau': 'Luau', '.py': 'Python', '.rs': 'Rust', '.ts': 'TypeScript',
    '.tsx': 'TypeScript', '.js': 'JavaScript', '.jsx': 'JavaScript',
    '.shader': 'ShaderLab', '.hlsl': 'HLSL', '.glsl': 'GLSL',
}
SCENES = {'.tscn', '.scn', '.unity', '.umap'}
DOCS = {
    'godot': 'https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html',
    'unity': 'https://docs.unity3d.com/Manual/EditorCommandLineArguments.html',
    'unreal': 'https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-automation-tool-overview-for-unreal-engine',
}


def _relative(workspace, path: Path) -> str:
    return path.relative_to(workspace.root).as_posix() or '.'


def _safe_file(workspace, path: Path) -> bool:
    """Use the existing workspace secret, symlink, and traversal policy."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
            return False
        workspace.resolve(_relative(workspace, path))
        return True
    except (ValueError, PermissionError, OSError):
        return False


def _manifest(workspace, path: Path) -> str:
    if not _safe_file(workspace, path):
        return ''
    try:
        return path.read_text(encoding='utf-8-sig')
    except (UnicodeError, OSError):
        return ''


def _match(text: str, pattern: str) -> str:
    found = re.search(pattern, text, flags=re.MULTILINE)
    return found.group(1)[:100].strip() if found else ''


def _engine(workspace, folder: Path) -> dict | None:
    if _safe_file(workspace, folder / 'project.godot'):
        config = _manifest(workspace, folder / 'project.godot')
        return {'engine': 'godot', 'name': _match(config, r'^config/name\s*=\s*"([^"\r\n]*)"') or folder.name,
                'version': '', 'manifest': 'project.godot'}
    if _safe_file(workspace, folder / 'ProjectSettings' / 'ProjectVersion.txt') and (folder / 'Assets').is_dir():
        version = _manifest(workspace, folder / 'ProjectSettings' / 'ProjectVersion.txt')
        return {'engine': 'unity', 'name': folder.name,
                'version': _match(version, r'^m_EditorVersion:\s*([^\r\n]+)'),
                'manifest': 'ProjectSettings/ProjectVersion.txt'}
    # A .uproject is the project marker; do not attempt to parse or run plugins.
    try:
        projects = sorted((p for p in islice(folder.iterdir(), MAX_SCAN_ENTRIES)
                           if p.suffix.lower() == '.uproject' and _safe_file(workspace, p)),
                          key=lambda p: p.name)
    except (OSError, PermissionError):
        return None
    if projects:
        data = _manifest(workspace, projects[0])
        try:
            details = json.loads(data)
            version = str(details.get('EngineAssociation', ''))[:100] if isinstance(details, dict) else ''
        except (ValueError, TypeError):
            version = ''
        return {'engine': 'unreal', 'name': projects[0].stem, 'version': version,
                'manifest': projects[0].name}
    return None


def _walk(workspace, root: Path, *, depth: int, budget: int):
    """Yield bounded descendants without following symlinks or generated folders."""
    stack = [(root, 0)]
    visited = 0
    while stack and visited < budget:
        folder, level = stack.pop()
        try:
            entries = sorted(islice(folder.iterdir(), budget), key=lambda p: p.name.lower())
        except (PermissionError, OSError):
            continue
        for entry in entries:
            visited += 1
            if visited > budget:
                return
            try:
                if entry.is_symlink():
                    continue
                workspace.resolve(_relative(workspace, entry))
                if entry.is_dir():
                    if level < depth and entry.name not in SKIP_DIRS:
                        stack.append((entry, level + 1))
                elif entry.is_file():
                    yield entry
            except (PermissionError, ValueError, OSError):
                continue


def _inventory(workspace, root: Path) -> dict:
    languages: dict[str, int] = {}
    scenes: list[str] = []
    for entry in _walk(workspace, root, depth=6, budget=MAX_SCAN_ENTRIES):
        extension = entry.suffix.lower()
        if extension in LANGUAGES:
            lang = LANGUAGES[extension]
            languages[lang] = languages.get(lang, 0) + 1
        if extension in SCENES and len(scenes) < 10:
            scenes.append(entry.relative_to(root).as_posix())
    return {'languages': dict(sorted(languages.items())), 'sample_scenes': scenes,
            'inventory_limited_to_entries': MAX_SCAN_ENTRIES}


def _details(workspace, folder: Path, *, inventory: bool = True) -> dict | None:
    found = _engine(workspace, folder)
    if found is None:
        return None
    result = {**found, 'path': _relative(workspace, folder)}
    if inventory:
        result.update(_inventory(workspace, folder))
    if found['engine'] == 'godot':
        result['export_presets'] = _presets(workspace, folder)
    elif found['engine'] == 'unity':
        manifest = _manifest(workspace, folder / 'Packages' / 'manifest.json')
        try:
            packages = json.loads(manifest).get('dependencies', {})
            result['package_count'] = min(len(packages), 10000) if isinstance(packages, dict) else 0
        except (ValueError, AttributeError, TypeError):
            result['package_count'] = 0
    return result


def discover(workspace, path: str = '.') -> dict:
    """Find direct and nested Godot, Unity, and Unreal projects in an approved directory."""
    root = workspace.resolve(path)
    if not root.is_dir():
        raise ValueError('Select a directory to discover game projects')
    projects: list[dict] = []
    # Scan up to three directory levels. Never descend into a recognized project.
    stack = [(root, 0)]
    visited = 0
    while stack and visited < MAX_SCAN_ENTRIES and len(projects) < MAX_PROJECTS:
        folder, level = stack.pop()
        visited += 1
        found = _details(workspace, folder, inventory=False)
        if found:
            projects.append(found)
            continue
        if level >= 3:
            continue
        try:
            entries = sorted(islice(folder.iterdir(), MAX_SCAN_ENTRIES),
                             key=lambda p: p.name.lower(), reverse=True)
        except (PermissionError, OSError):
            continue
        for p in entries:
            if p.name in SKIP_DIRS or p.is_symlink() or not p.is_dir():
                continue
            try:
                workspace.resolve(_relative(workspace, p))
            except (ValueError, PermissionError, OSError):
                continue
            stack.append((p, level + 1))
    return {'search_path': _relative(workspace, root), 'projects': projects,
            'scan_limited': visited >= MAX_SCAN_ENTRIES or len(projects) >= MAX_PROJECTS,
            'read_only': True}


def inspect(workspace, path: str) -> dict:
    folder = workspace.resolve(path)
    if not folder.is_dir():
        raise ValueError('Game project path must be a directory')
    found = _details(workspace, folder)
    if found is None:
        raise ValueError('No recognized game project at the selected directory')
    return {'project': found, 'read_only': True}


def _presets(workspace, folder: Path) -> list[str]:
    text = _manifest(workspace, folder / 'export_presets.cfg')
    # Presets are user content, not commands; only collect the name in each preset section.
    current = False
    names = []
    for line in text.splitlines():
        if re.match(r'^\[preset\.\d+\]$', line.strip()):
            current = True
        elif line.startswith('['):
            current = False
        elif current:
            name = _match(line, r'^name\s*=\s*"([^"\r\n]*)"')
            if name and name not in names and len(names) < 20:
                names.append(name)
    return names


def _output_path(workspace, folder: Path, value: str) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 200 or '\\' in value
            or ':' in value or Path(value).is_absolute() or '..' in Path(value).parts
            or any(ord(ch) < 32 for ch in value)):
        raise ValueError('Output must be a relative file inside the project')
    target = workspace.resolve(_relative(workspace, folder / value), allow_missing=True)
    if not target.is_relative_to(folder) or target == folder or target.suffix == '':
        raise ValueError('Output must be a file within the selected game project')
    return target.relative_to(folder).as_posix()


def plan(workspace, path: str, action: str, *, preset: str = '', output: str = '') -> dict:
    """Return an argv preview only; never spawn processes, scripts, or editor plugins."""
    folder = workspace.resolve(path)
    if not folder.is_dir():
        raise ValueError('Select a game project directory')
    found = _details(workspace, folder, inventory=False)
    if found is None:
        raise ValueError('No recognized game project at the selected directory')
    if action not in {'validate', 'import', 'test', 'export'}:
        raise ValueError('Unknown engine operation')
    engine = found['engine']
    result = {'engine': engine, 'project_path': found['path'], 'action': action,
              'available': False, 'executed': False, 'requires_owner_run': True,
              'executes_project_code': True, 'documentation': DOCS[engine],
              'notes': ['Preview only. STAR has not checked the editor installation, license, dependencies, or results.',
                        'Review project code, editor plugins, and output paths before running.']}
    if preset or output:
        if engine != 'godot' or action != 'export':
            raise ValueError('Preset and output are only allowed for Godot export')
    argv = None
    if engine == 'godot':
        if action == 'validate':
            argv = ['godot', '--headless', '--path', '.', '--editor', '--quit']
            result['notes'].append('Editor startup smoke check; not a complete syntax or gameplay test.')
        elif action == 'import':
            argv = ['godot', '--headless', '--path', '.', '--import']
        elif action == 'export':
            presets = _presets(workspace, folder)
            if not preset or preset not in presets:
                raise ValueError('Choose an existing export preset from the project manifest')
            if not output:
                raise ValueError('Provide an output filename inside the game project')
            target = _output_path(workspace, folder, output)
            argv = ['godot', '--headless', '--path', '.', '--export-release', preset, target]
            result['notes'].append('Export templates must be installed; the output parent directory must exist.')
        else:
            result['notes'].append('Godot has no universal project test runner; configure a specific test plugin and runner.')
    elif engine == 'unity':
        if action == 'validate':
            argv = ['<UNITY_EDITOR_EXECUTABLE>', '-batchmode', '-nographics', '-quit',
                    '-projectPath', '.', '-logFile', '-']
            result['notes'].append('Imports/compiles in editor batch mode; review Editor scripts and logs.')
        elif action == 'test':
            argv = ['<UNITY_EDITOR_EXECUTABLE>', '-batchmode', '-nographics',
                    '-projectPath', '.', '-runTests', '-testPlatform', 'EditMode',
                    '-testResults', 'star-editmode-results.xml', '-logFile', '-']
            result['notes'].append('Do not add -quit: it can interrupt Unity test runs.')
        else:
            result['notes'].append('Unity import and build use project-specific editor/Build Profiles configuration.')
    else:
        result['notes'].append('Unreal needs an installed editor/AutomationTool and target/platform-specific configuration.')
    if argv is not None:
        result.update(available=True, argv=argv, cwd=found['path'])
    return result
