"""One-to-one visual references: approved images the owner pins to a project.

- `pin` copies an image the owner chose into STAR's data folder (re-encoded PNG, no metadata).
- `for_turn` hands the pinned images to a chat turn that is about how something looks (a UI, a
  screen, an icon); image generation gets them through `star.image_gen`.
- `compare` puts a reference and STAR's output side by side, measures what can be measured
  locally (size, shape, colour, where the pixels differ) and asks the vision model for a short
  list of concrete differences. The measured part works with no model at all.

Nothing here judges "good enough": the owner approves. STAR only shows and lists.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import time
import uuid
from pathlib import Path
from typing import Callable

from ._lazy import lazy_attr, lazy_module
Image = lazy_attr("star.pil_safe", "Image")   # Pillow loads on first use, with the pixel limit set
ImageChops, ImageDraw = lazy_module("PIL.ImageChops"), lazy_module("PIL.ImageDraw")
ImageOps, ImageStat = lazy_module("PIL.ImageOps"), lazy_module("PIL.ImageStat")

MAX_REFERENCES = 12                 # per project
MAX_SIDE = 2048                     # stored copy; larger images are scaled down
MAX_SOURCE_BYTES = 25_000_000
TURN_LIMIT = 2                      # references attached to one chat turn or one generation
_ID = re.compile(r'^[a-f0-9]{12}$')
_GRID = (('top left', 'top', 'top right'), ('left', 'centre', 'right'),
         ('bottom left', 'bottom', 'bottom right'))

# A turn that is about how something looks. Deliberately narrow: attaching pictures makes a
# CPU server read them first, which costs seconds per image.
VISUAL_TURN = re.compile(
    r'\b(?:ui|gui|hud|interface|screen|menu|layout|mock-?up|button|frame|panel|shop|inventory|'
    r'lobby|icon|logo|thumbnail|banner|style|theme|colou?rs?|palette|look(?:s|ing)?|design|'
    r'reference|match|one[- ]to[- ]one|1[:\-]1|pixel[- ]perfect)\b', re.I)


def _folder(home: Path, project: str) -> Path:
    name = re.sub(r'[^A-Za-z0-9._-]+', '-', str(project)).strip('-.')[:60] or 'project'
    digest = hashlib.sha256(str(project).encode('utf-8')).hexdigest()[:8]
    return home / 'references' / f'{name}-{digest}'


def _load(folder: Path) -> list[dict]:
    index = folder / 'index.json'
    if not index.is_file():
        return []
    try:
        rows = json.loads(index.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return [row for row in rows if isinstance(row, dict) and _ID.fullmatch(str(row.get('id', '')))
            and (folder / f"{row['id']}.png").is_file()]


def _save(folder: Path, rows: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / 'index.json.tmp'
    temporary.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    temporary.replace(folder / 'index.json')


def _open(path: Path) -> Image.Image:
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError('Image missing or larger than 25 MB')
    try:
        source = Image.open(path)
    except (OSError, ValueError) as exc:          # not a picture at all
        raise ValueError('Use a PNG, JPEG or WebP image') from exc
    with source:
        if source.format not in {'PNG', 'JPEG', 'WEBP'}:
            raise ValueError('Use a PNG, JPEG or WebP image')
        if getattr(source, 'n_frames', 1) != 1 or source.width * source.height > 40_000_000:
            raise ValueError("Animated images or images over 40 MP aren't supported")
        return ImageOps.exif_transpose(source).convert('RGB')


def _thumb(image: Image.Image, side: int = 360) -> str:
    import base64
    small = image.copy()
    small.thumbnail((side, side), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    small.save(out, format='WEBP', quality=74, method=4)
    return 'data:image/webp;base64,' + base64.b64encode(out.getvalue()).decode('ascii')


def pin(home: Path, project: str, source: Path, *, label: str = '', note: str = '') -> dict:
    """Copy an approved image into the project's references. Returns its entry."""
    image = _open(source)
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    folder = _folder(home, project)
    rows = _load(folder)
    if len(rows) >= MAX_REFERENCES:
        raise ValueError(f'A project keeps at most {MAX_REFERENCES} references. Remove one first.')
    encoded = io.BytesIO()
    image.save(encoded, format='PNG')
    digest = hashlib.sha256(encoded.getvalue()).hexdigest()
    if any(row.get('sha256') == digest for row in rows):
        raise ValueError('This image is already pinned to the project')
    entry = {'id': uuid.uuid4().hex[:12],
             'label': (str(label).strip() or Path(source).stem)[:80],
             'note': str(note).strip()[:400],
             'width': image.width, 'height': image.height, 'sha256': digest,
             'added': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{entry['id']}.png").write_bytes(encoded.getvalue())
    _save(folder, rows + [entry])
    return entry


def unpin(home: Path, project: str, reference_id: str) -> bool:
    """Remove STAR's copy of one reference (the owner's original file is never touched)."""
    if not _ID.fullmatch(str(reference_id)):
        raise ValueError('Unknown reference')
    folder = _folder(home, project)
    rows = _load(folder)
    kept = [row for row in rows if row['id'] != reference_id]
    if len(kept) == len(rows):
        return False
    _save(folder, kept)
    (folder / f'{reference_id}.png').unlink(missing_ok=True)
    return True


def entries(home: Path, project: str) -> list[dict]:
    return _load(_folder(home, project))


def listing(home: Path, project: str) -> list[dict]:
    """Entries with a small preview each, for the interface."""
    folder = _folder(home, project)
    shown = []
    for row in _load(folder):
        try:
            with Image.open(folder / f"{row['id']}.png") as image:
                preview = _thumb(image.convert('RGB'))
        except OSError:
            continue
        shown.append({**{k: row.get(k) for k in ('id', 'label', 'note', 'width', 'height', 'added')},
                      'preview': preview})
    return shown


def path_of(home: Path, project: str, reference_id: str) -> Path:
    if not _ID.fullmatch(str(reference_id)):
        raise ValueError('Unknown reference')
    path = _folder(home, project) / f'{reference_id}.png'
    if not path.is_file():
        raise ValueError('Unknown reference')
    return path


def paths(home: Path, project: str, limit: int = TURN_LIMIT) -> list[tuple[dict, Path]]:
    folder = _folder(home, project)
    return [(row, folder / f"{row['id']}.png") for row in _load(folder)[:max(0, limit)]]


def for_turn(home: Path, project: str, prompt: str, *, already: int = 0, cap: int = 4,
             enabled: bool = True) -> tuple[list[Path], str]:
    """References to attach to a chat turn about how something looks, with the line that says so.

    ([], '') when the project has none, the turn is not about looks, or there is no room.
    """
    room = min(TURN_LIMIT, cap - already)
    if not enabled or room <= 0 or not VISUAL_TURN.search(prompt or ''):
        return [], ''
    chosen = paths(home, project, room)
    if not chosen:
        return [], ''
    names = '; '.join(f"{i}. {row['label']}" + (f" ({row['note']})" if row.get('note') else '')
                      for i, (row, _) in enumerate(chosen, 1))
    count = len(chosen)
    line = (f"Approved visual reference{'s' if count != 1 else ''} for this project "
            f"({'the last ' + str(count) + ' images' if count != 1 else 'the last image'} attached): {names}. "
            'The owner approved these: match their layout, proportions, colours and style one-to-one '
            'unless the message says otherwise, and say plainly where you cannot.')
    return [path for _, path in chosen], line


# ---- compare ---------------------------------------------------------------------------------

def side_by_side(reference: Path, candidate: Path, destination: Path, *, height: int = 768) -> Path:
    """Write a labelled reference | output picture and return its path."""
    left, right = _open(reference), _open(candidate)

    def fit(image: Image.Image) -> Image.Image:
        width = max(1, round(image.width * height / image.height))
        return image.resize((min(width, height * 3), height), Image.Resampling.LANCZOS)

    left, right = fit(left), fit(right)
    bar, gap = 34, 12
    sheet = Image.new('RGB', (left.width + right.width + gap, height + bar), (18, 20, 26))
    sheet.paste(left, (0, bar))
    sheet.paste(right, (left.width + gap, bar))
    draw = ImageDraw.Draw(sheet)
    draw.text((10, 10), 'REFERENCE (approved)', fill=(240, 205, 120))
    draw.text((left.width + gap + 10, 10), "STAR'S OUTPUT", fill=(170, 200, 255))
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, format='PNG')
    return destination


def measure(reference: Path, candidate: Path) -> dict:
    """What can be said about two pictures without a model: shape, colour, where they differ."""
    ref, out = _open(reference), _open(candidate)
    facts: dict = {'reference_size': [ref.width, ref.height], 'output_size': [out.width, out.height]}
    ratio_ref, ratio_out = ref.width / ref.height, out.width / out.height
    facts['aspect_ratio'] = {'reference': round(ratio_ref, 3), 'output': round(ratio_out, 3)}
    side = 96
    a = ref.resize((side, side), Image.Resampling.BILINEAR)
    b = out.resize((side, side), Image.Resampling.BILINEAR)
    difference = ImageChops.difference(a, b).convert('L')
    facts['difference_percent'] = round(ImageStat.Stat(difference).mean[0] / 255 * 100, 1)
    cell = side // 3
    regions = []
    for row in range(3):
        for column in range(3):
            box = (column * cell, row * cell, (column + 1) * cell, (row + 1) * cell)
            regions.append((round(ImageStat.Stat(difference.crop(box)).mean[0] / 255 * 100, 1),
                            _GRID[row][column]))
    facts['most_different_regions'] = [{'region': name, 'difference_percent': value}
                                       for value, name in sorted(regions, reverse=True)[:3] if value >= 3]
    mean_ref, mean_out = ImageStat.Stat(a).mean, ImageStat.Stat(b).mean
    facts['average_colour'] = {'reference': '#%02x%02x%02x' % tuple(round(v) for v in mean_ref),
                               'output': '#%02x%02x%02x' % tuple(round(v) for v in mean_out)}
    brightness = (sum(mean_out) - sum(mean_ref)) / 3 / 255 * 100
    facts['brightness_change_percent'] = round(brightness, 1)
    lines = []
    if abs(ratio_ref - ratio_out) / ratio_ref > 0.02:
        lines.append(f'Shape differs: the reference is {ref.width}x{ref.height} (ratio {ratio_ref:.2f}), '
                     f'the output is {out.width}x{out.height} (ratio {ratio_out:.2f}).')
    if abs(brightness) >= 4:
        lines.append(f"The output is {abs(brightness):.0f}% {'brighter' if brightness > 0 else 'darker'} overall "
                     f"(average colour {facts['average_colour']['output']} against {facts['average_colour']['reference']}).")
    if facts['most_different_regions']:
        lines.append('Largest pixel differences: ' + ', '.join(
            f"{item['region']} ({item['difference_percent']}%)" for item in facts['most_different_regions']) + '.')
    if facts['difference_percent'] < 1.5 and not lines:
        lines.append('No measurable difference at this scale (under 1.5% of the pixel range).')
    facts['lines'] = lines
    return facts


COMPARE_QUESTION = (
    'Two pictures follow. Picture 1 is the APPROVED REFERENCE. Picture 2 is the OUTPUT that should match it '
    'one-to-one. List the concrete visible differences in picture 2 compared with picture 1, most important '
    'first, at most 8. One difference per line, each line starting with "- ". Name the element and say what '
    'differs (position, size, colour, text, spacing, shape, missing or extra element). Use only what is '
    'visible. Do not praise, do not suggest fixes, do not describe what matches. If you see no difference, '
    'answer exactly: - No visible difference.')


def _bullets(text: str, limit: int = 8) -> list[str]:
    found = []
    for line in text.splitlines():
        cleaned = re.sub(r'^\s*(?:[-*•]|\d+[.)])\s*', '', line).strip()
        if cleaned and (line.lstrip().startswith(('-', '*', '•')) or re.match(r'^\s*\d+[.)]', line)):
            found.append(cleaned[:300])
    if not found and text.strip():
        found = [text.strip()[:300]]
    return found[:limit]


def compare(settings, home: Path, project: str, reference_id: str, candidate: Path, *,
            ask: Callable | None = None, cancelled: Callable[[], bool] | None = None) -> dict:
    """Side-by-side picture, measured facts, and the vision model's list of differences.

    If the vision model cannot be reached the measured part is still returned and
    `model_error` says why: nothing is made up in its place.
    """
    reference = path_of(home, project, reference_id)
    candidate = Path(candidate)
    row = next((row for row in entries(home, project) if row['id'] == reference_id), {})
    stamp = time.strftime('%Y%m%dT%H%M%S', time.gmtime())
    sheet = side_by_side(reference, candidate, home / 'comparisons' / f'{stamp}-{reference_id}.png')
    result: dict = {'reference': {'id': reference_id, 'label': row.get('label', '')},
                    'side_by_side': sheet, 'measured': measure(reference, candidate),
                    'differences': [], 'model': '', 'seconds': 0.0, 'model_error': ''}
    if ask is None:
        from .vision import ask as ask
    try:
        seen = ask(settings, COMPARE_QUESTION, [reference, candidate], max_tokens=420,
                   **({'cancelled': cancelled} if cancelled else {}))
        result.update(differences=_bullets(seen.text), model=seen.model, seconds=seen.seconds)
    except Exception as exc:                      # the measured facts and the picture still stand
        if cancelled is not None and cancelled():
            raise
        result['model_error'] = f'{type(exc).__name__}: {str(exc)[:240]}'
    return result
