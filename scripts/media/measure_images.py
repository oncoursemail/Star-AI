"""Measure STAR's image generation on this PC's graphics card through the real code path.

    python scripts/media/measure_images.py --home <empty folder> --out measurements.json

Needs ComfyUI running on 127.0.0.1 (scripts/media/start_comfyui.sh). Each size is generated
`--runs` times with fixed seeds; the first run after `--cold` (models unloaded) is reported
separately. Graphics memory is sampled from nvidia-smi four times a second while a job runs.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image, ImageDraw  # noqa: E402

from star import image_gen, references  # noqa: E402
from star.comfy import ComfyClient  # noqa: E402
from star.desktop_core import Settings  # noqa: E402

PROMPT = ('A cosy low-poly island shop for a Roblox game, wooden sign, warm lantern light at dusk, '
          'clean game art, soft shadows')


class MemoryWatch:
    """Peak `memory.used` of the first NVIDIA card while the block runs (whole card, all programs)."""

    def __init__(self):
        self.peak, self.before = 0, self._read()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    @staticmethod
    def _read() -> int:
        try:
            out = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                                 capture_output=True, text=True, timeout=5).stdout
            return int(out.strip().splitlines()[0])
        except Exception:
            return 0

    def _loop(self):
        while not self._stop.is_set():
            self.peak = max(self.peak, self._read())
            self._stop.wait(0.25)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join(timeout=3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--home', required=True, help='empty folder used as the STAR data folder')
    parser.add_argument('--out', required=True)
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--port', type=int, default=8188)
    args = parser.parse_args()
    home = Path(args.home)
    home.mkdir(parents=True, exist_ok=True)
    settings = Settings(project='measure', comfy_port=args.port)
    report: dict = {'date': time.strftime('%Y-%m-%d', time.gmtime()), 'prompt': PROMPT, 'runs': args.runs}
    with ComfyClient(port=args.port) as comfy:
        report['comfyui'] = comfy.status()
        comfy.free()
    time.sleep(3)
    idle = MemoryWatch._read()
    report['vram_idle_mb'] = idle

    def timed(label: str, **kwargs) -> dict:
        with MemoryWatch() as watch:
            started = time.monotonic()
            result = image_gen.generate(settings, kwargs.pop('prompt', PROMPT), home, **kwargs)
            seconds = round(time.monotonic() - started, 2)
        row = {'label': label, 'seconds': seconds, 'vram_peak_mb': watch.peak,
               'size': [result['note']['width'], result['note']['height']], 'file': result['path'].name}
        print(json.dumps(row), flush=True)
        return row

    rows = [timed('first image after models were unloaded (1024x1024)', size='square', seed=1)]
    for size in image_gen.SIZES:
        for run in range(args.runs):
            rows.append(timed(f'text {size} run {run + 1}', size=size, seed=100 + run))
    source = image_gen.latest(home)
    for run in range(args.runs):
        rows.append(timed(f'edit run {run + 1}', prompt='Make it snow: snow on the roof and the ground, cold blue evening light',
                          source=source, seed=200 + run))
    mask = home / 'mask.png'
    with Image.open(source) as opened:
        blank = Image.new('L', opened.size, 0)
    ImageDraw.Draw(blank).rectangle((blank.width // 3, blank.height // 3, blank.width * 2 // 3, blank.height * 2 // 3), fill=255)
    blank.save(mask)
    for run in range(args.runs):
        rows.append(timed(f'inpaint run {run + 1}', prompt='A bright red door with a round window',
                          source=source, mask=mask, seed=300 + run))
    references.pin(home, settings.project, source, label='island shop')
    for run in range(args.runs):
        rows.append(timed(f'text square with 1 pinned reference run {run + 1}',
                          prompt='The same shop seen from the left side at night, lanterns glowing',
                          size='square', seed=400 + run))
    report['rows'] = rows
    report['vram_peak_mb'] = max(row['vram_peak_mb'] for row in rows)
    Path(args.out).write_text(json.dumps(report, indent=1), encoding='utf-8')
    print('written', args.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
