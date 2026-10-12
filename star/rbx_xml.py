"""Read-only, bounded Roblox XML evidence. Never runs Luau or resolves assets.

Paths use percent-encoded name segments, with [1], [2], ... for duplicate
siblings. An empty name is %00. Paths are opaque instance identifiers, not
filesystem paths or XPath. Script summaries are lexical hints, not analysis
of dynamic calls, alias resolution, or proof that a script is safe.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
from typing import Callable
from urllib.parse import quote
from xml.etree.ElementTree import ParseError, TreeBuilder

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import DefusedXMLParser

XML_EXTENSIONS = frozenset({'.rbxmx', '.rbxlx'})
BINARY_EXTENSIONS = frozenset({'.rbxm', '.rbxl'})
BINARY_MESSAGE = 'Binary Roblox .rbxm/.rbxl files are not supported; export as XML .rbxmx/.rbxlx in Roblox Studio.'
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_XML_DEPTH = 64
MAX_ELEMENTS = 200_000
MAX_INSTANCES = 20_000
MAX_TEXT_CHARS = 2_000_000
MAX_NAME_CHARS = 256
MAX_PATH_CHARS = 4096
SCRIPT_CLASSES = frozenset({'Script', 'LocalScript', 'ModuleScript'})
USEFUL_PROPERTIES = frozenset({
    'Archivable', 'Disabled', 'Enabled', 'RunContext', 'Anchored', 'CanCollide',
    'CanQuery', 'CanTouch', 'Massless', 'Transparency', 'Reflectance', 'Size',
    'Position', 'CFrame', 'Color', 'Color3uint8', 'BrickColor', 'Material', 'Shape',
    'MeshId', 'TextureID', 'TextureId', 'SoundId', 'Volume', 'PlaybackSpeed',
    'Looped', 'Text', 'TextSize', 'TextColor3', 'BackgroundColor3',
    'BackgroundTransparency', 'Visible', 'LayoutOrder', 'ZIndex', 'Value',
    'PrimaryPart',
})
_COMPONENTS = {
    'Vector2': ('X', 'Y'), 'Vector3': ('X', 'Y', 'Z'),
    'Color3': ('R', 'G', 'B'), 'UDim': ('S', 'O'),
    'UDim2': ('XS', 'XO', 'YS', 'YO'),
    'CoordinateFrame': ('X', 'Y', 'Z', 'R00', 'R01', 'R02', 'R10', 'R11', 'R12', 'R20', 'R21', 'R22'),
}
_IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
_LONG = re.compile(r'\[(=*)\[')
_REMOTE_METHODS = frozenset({'FireServer', 'FireClient', 'FireAllClients', 'InvokeServer', 'InvokeClient'})
_REMOTE_EVENTS = frozenset({'OnServerEvent', 'OnClientEvent', 'OnServerInvoke', 'OnClientInvoke'})


class RbxXMLError(ValueError):
    """Unsupported, malformed, or over-budget Roblox XML."""


def _budget(value: int) -> None:
    if type(value) is not int or value < 0:
        raise RbxXMLError('Budget and outline limits must be nonnegative integers')


def _short(value: str, limit: int = 160) -> str:
    text = ' '.join(value.replace('[STAR', '(STAR').replace('[END STAR', '(END STAR').split())
    return text if len(text) <= limit else text[:limit - 3] + '...'


class _BoundedBuilder(TreeBuilder):
    def __init__(self, check: Callable[[], None]):
        super().__init__()
        self.check = check
        self.tags: list[str] = []
        self.elements = self.instances = self.chars = 0

    def start(self, tag, attrs):
        self.check()
        self.elements += 1
        if len(self.tags) >= MAX_XML_DEPTH:
            raise RbxXMLError('Roblox XML exceeds the XML depth limit')
        if self.elements > MAX_ELEMENTS:
            raise RbxXMLError('Roblox XML exceeds the element-count limit')
        if tag == 'Item':
            self.instances += 1
            if self.instances > MAX_INSTANCES:
                raise RbxXMLError('Roblox XML exceeds the instance-count limit')
            if not self.tags or self.tags[-1] not in {'roblox', 'Item'}:
                raise RbxXMLError('Roblox Item must be a direct child of roblox or Item')
        self.tags.append(tag)
        return super().start(tag, attrs)

    def end(self, tag):
        element = super().end(tag)
        self.tags.pop()
        return element

    def data(self, data):
        self.check()
        self.chars += len(data)
        if self.chars > MAX_TEXT_CHARS:
            raise RbxXMLError('Roblox XML exceeds the text-character limit')
        super().data(data)


def _number(text: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise RbxXMLError('Invalid numeric Roblox property') from exc
    if not math.isfinite(value):
        raise RbxXMLError('Non-finite Roblox property is not supported')
    return value


def _property(element):
    tag, text = element.tag, element.text or ''
    if tag in _COMPONENTS:
        values = {}
        for component in _COMPONENTS[tag]:
            children = element.findall(component)
            if len(children) != 1 or len(children[0]):
                raise RbxXMLError('Invalid compound Roblox property')
            values[component] = _number(children[0].text or '')
        return {'type': tag, **values}
    if tag == 'Content':
        # Retain the identifier only; never retrieve a URL or asset.
        url = element.find('url')
        return _short(url.text or '', 1000) if url is not None else None
    if len(element):
        return None
    if tag == 'bool':
        if text.strip() not in {'true', 'false'}:
            raise RbxXMLError('Invalid boolean Roblox property')
        return text.strip() == 'true'
    if tag in {'int', 'int64', 'token', 'Color3uint8'}:
        try:
            return int(text.strip())
        except ValueError as exc:
            raise RbxXMLError('Invalid integer Roblox property') from exc
    if tag in {'float', 'double'}:
        return _number(text)
    if tag in {'string', 'Ref'}:
        return _short(text, 1000)
    return None


def _tokens(source: str) -> list[tuple[str, str]]:
    """Small linear lexer: skip comments and isolate strings before looking at calls.

    Backtick interpolations are intentionally opaque. Escaped literal names are
    not decoded with Python/Luau execution; unusual escapes remain lexical hints.
    """
    result, index = [], 0
    while index < len(source):
        char = source[index]
        comment = source.startswith('--', index)
        start = index + 2 if comment else index
        long = _LONG.match(source, start)
        if long:
            end = source.find(']' + long[1] + ']', long.end())
            stop = len(source) if end < 0 else end
            if not comment:
                result.append(('string', source[long.end():stop]))
            index = len(source) if end < 0 else end + len(long[1]) + 2
        elif comment:
            end = source.find('\n', start)
            index = len(source) if end < 0 else end
        elif char in {'\"', "'", '`'}:
            end = index + 1
            while end < len(source):
                if source[end] == '\\':
                    end += 2
                elif source[end] == char:
                    break
                else:
                    end += 1
            result.append(('opaque' if char == '`' else 'string', source[index + 1:end]))
            index = min(len(source), end + 1)
        elif char.isspace():
            index += 1
        else:
            word = _IDENT.match(source, index)
            if word:
                result.append(('id', word[0]))
                index = word.end()
            else:
                result.append(('symbol', char))
                index += 1
    return result


def _receiver(tokens, end: int) -> str:
    if end < 0 or tokens[end][0] != 'id':
        return '(expression)'
    start = end
    while start >= 2 and tokens[start - 1][1] == '.' and tokens[start - 2][0] == 'id':
        start -= 2
    return _short(''.join(value for _, value in tokens[start:end + 1]))


def summarize_script(source: str) -> str:
    tokens = _tokens(source)
    services, required, remotes, functions = set(), set(), set(), set()
    for index, (kind, value) in enumerate(tokens):
        if kind != 'id':
            continue
        previous = tokens[index - 1][1] if index else ''
        after = tokens[index + 1:index + 3]
        if value == 'GetService' and previous in {':', '.'} and len(after) == 2:
            if after[0][1] == '(' and after[1][0] == 'string':
                services.add(_short(after[1][1]))
        if value == 'require' and previous not in {':', '.'} and after and after[0][1] == '(':
            expression = []
            for token_kind, token in tokens[index + 2:index + 26]:
                if token == ')':
                    required.add(_short(''.join(expression)))
                    break
                if token_kind in {'string', 'opaque'} or token in {'(', ',', '{'}:
                    break
                expression.append(token)
        if (value in _REMOTE_METHODS and previous == ':' and after and after[0][1] == '('
                or value in _REMOTE_EVENTS and previous == '.'):
            remotes.add(f'{_receiver(tokens, index - 2)}{previous}{value}')
        if value == 'function':
            names = []
            for token_kind, token in tokens[index + 1:index + 26]:
                if token == '(':
                    if names:
                        functions.add(_short(''.join(names)))
                    elif previous == '=':
                        functions.add(_receiver(tokens, index - 2))
                    break
                if token_kind != 'id' and token not in {'.', ':'}:
                    break
                names.append(token)
    def listed(values):
        ordered = sorted(value for value in values if value)
        text = ', '.join(ordered[:8]) or 'none detected'
        return text + (f' (+{len(ordered) - 8} more)' if len(ordered) > 8 else '')
    text = '; '.join(f'{label}: {listed(values)}' for label, values in (
        ('services', services), ('requires', required), ('remotes', remotes), ('functions', functions)))
    return _clip(text, 1200, '[Further lexical hints omitted.]')


@dataclass
class Instance:
    class_name: str
    name: str
    properties: dict = field(default_factory=dict)
    children: list[Instance] = field(default_factory=list)
    source: str | None = None
    path: str = ''
    segment: str = ''
    descendants: int = 0
    script_count: int = 0


@dataclass(frozen=True)
class Script:
    path: str
    kind: str
    line_count: int
    summary: str
    source: str | None = field(repr=False)


@dataclass
class RobloxFile:
    roots: list[Instance]
    instances: dict[str, Instance]
    scripts: list[Script]
    warnings: list[str]

    def script_list(self) -> list[dict]:
        return [{'path': item.path, 'kind': item.kind, 'line_count': item.line_count,
                 'summary': item.summary, 'source_available': item.source is not None}
                for item in self.scripts]

    def evidence(self):
        """Ordered (source location, text, kind) units for the document pipeline."""
        yield 'Roblox outline', self.outline(), 'rbx_outline'
        for item in self.scripts:
            yield ('Roblox script index',
                   f'{item.path} [{item.kind}]: {item.line_count} lines; {item.summary}',
                   'rbx_script_index')
        for item in self.instances.values():
            if item.properties:
                yield ('Roblox properties',
                       f'{item.path} [{item.class_name}] properties: '
                       + json.dumps(item.properties, ensure_ascii=False, sort_keys=True),
                       'rbx_properties')
        for item in self.scripts:
            if item.source is not None:
                lines = item.source.splitlines(keepends=True)
                for offset in range(0, len(lines), 40):
                    end = min(offset + 40, len(lines))
                    yield (f'lines {offset + 1}-{end}, {item.kind}, path {item.path}',
                           ''.join(lines[offset:end]), 'rbx_source')

    def find(self, path: str) -> Instance:
        if not isinstance(path, str) or path not in self.instances:
            raise RbxXMLError('Instance path not found; use an exact path from the outline/script list')
        return self.instances[path]

    def outline(self, *, max_depth: int = 6, max_nodes: int = 200,
                budget_chars: int = 8000, path: str | None = None) -> str:
        for value in (max_depth, max_nodes, budget_chars):
            _budget(value)
        roots = self.roots if path is None else [self.find(path)]
        total = sum(1 + item.descendants for item in roots)
        scripts = sum(item.script_count for item in roots)
        lines = [f'Roblox XML outline: {total} instances; {scripts} scripts.']
        pending = [(item, 0) for item in reversed(roots)]
        shown = 0
        while pending and shown < max_nodes:
            item, depth = pending.pop()
            lines.append(f'{"  " * depth}{item.segment} [{item.class_name}] '
                         f'({len(item.children)} children; {item.descendants} descendants; {item.script_count} scripts)')
            shown += 1
            if depth < max_depth:
                pending.extend((child, depth + 1) for child in reversed(item.children))
        if shown < total:
            lines.append(f'[{total - shown} instances omitted by outline depth/node limits.]')
        return _clip('\n'.join(lines), budget_chars, '[Outline excerpt ends; more instances may be omitted.]')

    def focus(self, path: str, *, budget_chars: int = 6000, max_depth: int = 6) -> str:
        """Extract one exact subtree/script, outline and metadata before source bodies."""
        _budget(budget_chars)
        node = self.find(path)
        selected = [script for script in self.scripts
                    if script.path == node.path or script.path.startswith(node.path + '/')]
        parts = [f'Roblox focus: {path} (untrusted source; never executed)',
                 self.outline(path=path, max_depth=max_depth, budget_chars=budget_chars)]
        for item in selected:
            parts.append(f'{item.kind} {item.path}: {item.line_count} lines; {item.summary}')
        for item in self.instances.values():
            if (item.path == path or item.path.startswith(path + '/')) and item.properties:
                parts.append(f'{item.path} properties: {json.dumps(item.properties, ensure_ascii=False, sort_keys=True)}')
        for item in selected:
            if item.source is not None:
                parts.append(f'--- Source: {item.path} ---\n{item.source}')
        return _clip('\n\n'.join(parts), budget_chars, '[Focus excerpt ends; remaining source omitted for this budget.]')


def _clip(text: str, budget: int, marker: str) -> str:
    if len(text) <= budget:
        return text
    if budget <= len(marker):
        return marker[:budget]
    return text[:budget - len(marker) - 1] + '\n' + marker


def read(path: Path, *, suffix: str | None = None,
         check: Callable[[], None] | None = None) -> RobloxFile:
    """Read a regular XML file; suffix may identify a suffixless immutable artifact."""
    path = Path(path)
    extension = (suffix if suffix is not None else path.suffix).lower()
    if extension in BINARY_EXTENSIONS:
        raise RbxXMLError(BINARY_MESSAGE)
    if extension not in XML_EXTENSIONS:
        raise RbxXMLError('Choose a Roblox XML .rbxmx or .rbxlx file')
    check = check or (lambda: None)
    check()
    builder = _BoundedBuilder(check)
    parser = DefusedXMLParser(target=builder, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    try:
        if path.is_symlink() or not path.is_file():
            raise RbxXMLError('Roblox XML input must be a regular file, not a symlink')
        if path.stat().st_size > MAX_FILE_BYTES:
            raise RbxXMLError('Roblox XML exceeds the 16 MiB file-size limit')
        with path.open('rb') as stream:
            consumed = 0
            while True:
                check()
                raw = stream.read(min(65536, MAX_FILE_BYTES - consumed + 1))
                if not raw:
                    break
                if consumed == 0 and raw.lstrip().startswith(b'<roblox!'):
                    raise RbxXMLError(BINARY_MESSAGE)
                consumed += len(raw)
                if consumed > MAX_FILE_BYTES:
                    raise RbxXMLError('Roblox XML exceeds the file-size limit')
                parser.feed(raw)
        root = parser.close()
    except DefusedXmlException as exc:
        raise RbxXMLError('Unsafe Roblox XML: DTDs, entities and external references are forbidden') from exc
    except ParseError as exc:
        raise RbxXMLError('Malformed Roblox XML') from exc
    except OSError as exc:
        raise RbxXMLError('Could not read the Roblox XML file') from exc
    if root.tag != 'roblox' or root.get('version', '4') != '4':
        raise RbxXMLError('Expected a Roblox XML version 4 <roblox> root')
    warnings = []
    def build(element):
        check()
        class_name = element.get('class', '')
        if len(class_name) > 80 or not _IDENT.fullmatch(class_name):
            raise RbxXMLError('Invalid or missing Roblox instance class')
        node = Instance(class_name, class_name)
        groups = element.findall('Properties')
        if len(groups) > 1:
            raise RbxXMLError('Duplicate Roblox Properties block')
        seen = set()
        for prop in groups[0] if groups else []:
            name = prop.get('name', '')
            if name not in USEFUL_PROPERTIES and name not in {'Name', 'Source'}:
                continue
            if name in seen:
                raise RbxXMLError('Duplicate useful Roblox property')
            seen.add(name)
            if name == 'Name':
                if prop.tag != 'string' or len(prop) or len(prop.text or '') > MAX_NAME_CHARS:
                    raise RbxXMLError('Invalid or oversized Roblox instance name')
                node.name = prop.text or ''
            elif name == 'Source':
                if node.class_name in SCRIPT_CLASSES and prop.tag in {'ProtectedString', 'string'} and not len(prop):
                    node.source = prop.text or ''
            else:
                value = _property(prop)
                if value is not None:
                    node.properties[name] = value
        node.children = [build(child) for child in element.findall('Item')]
        node.descendants = sum(1 + child.descendants for child in node.children)
        node.script_count = int(class_name in SCRIPT_CLASSES) + sum(child.script_count for child in node.children)
        return node
    roots = [build(element) for element in root.findall('Item')]
    instances, scripts = {}, []
    def index_nodes(siblings, parent=''):
        counts, used = Counter(item.name for item in siblings), Counter()
        for item in siblings:
            check()
            used[item.name] += 1
            segment = quote(item.name, safe='') or '%00'
            if counts[item.name] > 1:
                segment += f'[{used[item.name]}]'
            item.segment = segment
            item.path = parent + '/' + segment
            if len(item.path) > MAX_PATH_CHARS:
                raise RbxXMLError('Roblox instance path exceeds the path-character limit')
            instances[item.path] = item
            if item.class_name in SCRIPT_CLASSES:
                summary = summarize_script(item.source) if item.source is not None else 'Inline source unavailable; external/shared source is not fetched.'
                if item.source is None:
                    warnings.append(f'Source unavailable for {item.path}')
                scripts.append(Script(item.path, item.class_name, len(item.source.splitlines()) if item.source else 0,
                                      summary, item.source))
            index_nodes(item.children, item.path)
    index_nodes(roots)
    return RobloxFile(roots, instances, scripts, warnings)
