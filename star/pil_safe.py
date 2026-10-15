"""Pillow's `PIL.Image`, with STAR's decompression-bomb limit applied when it is first loaded.

Modules that handle pictures bind `Image = lazy_attr("star.pil_safe", "Image")`, so Pillow is not imported when the
desktop starts (proposal #325 item 21) and the limit is set before any STAR code can open an image. It used to be
set as a side effect of importing `star.media` at start-up.
"""
from PIL import Image as _PILImage

from .media import MAX_PIXELS

Image = _PILImage   # a plain name, so `from star.pil_safe import Image` type-checks even without Pillow installed

Image.MAX_IMAGE_PIXELS = MAX_PIXELS
