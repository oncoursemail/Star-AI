"""A Discord reply that grows while the model writes it.

The first text is posted as soon as it arrives and the same message is then
edited, at most once per `interval` seconds (Discord allows about five edits per
five seconds per channel). No discord.py import: the bot hands in `post` and
`edit` coroutines, so this is tested offline. A failed post or edit (rate limit,
deleted message) switches the live view off; the bot then sends the full answer
the normal way, so nothing is lost.
"""
from __future__ import annotations

import logging
import time

_LOG = logging.getLogger(__name__)
CURSOR = " ▌"


def preview(text: str, limit: int) -> str:
    """The start of a partial answer that fits `limit`, with an open code block closed."""
    text = text.strip()
    if len(text) > limit - 40:
        text = text[: limit - 40].rstrip() + " …"
    if text.count("```") % 2:
        text += "\n```"
    return text + CURSOR


class LiveReply:
    def __init__(self, post, edit, *, interval: float = 1.2, limit: int = 1900, clock=time.monotonic) -> None:
        self._post, self._edit = post, edit
        self.interval, self.limit, self._clock = interval, limit, clock
        self.handle = None          # whatever `post` returned (the Discord message)
        self.broken = False
        self.edits = 0
        self._last = 0.0
        self._shown = ""

    @property
    def live(self) -> bool:
        """A message was posted and still accepts edits."""
        return self.handle is not None and not self.broken

    async def _show(self, text: str) -> None:
        try:
            if self.handle is None:
                self.handle = await self._post(text)
                if self.handle is None:
                    self.broken = True
            else:
                await self._edit(self.handle, text)
                self.edits += 1
        except Exception as exc:     # never let the live view break the answer itself
            _LOG.info("Live Discord reply stopped (%s); the answer is sent in full at the end", type(exc).__name__)
            self.broken = True
        self._last = self._clock()
        self._shown = text

    async def status(self, note: str) -> None:
        """A short note (for example 'queued') before the first answer text."""
        if not self.broken and not self._shown.endswith(CURSOR):
            await self._show(note)

    async def update(self, text: str) -> None:
        """Called with the whole answer so far after every streamed piece."""
        if self.broken or not text.strip():
            return
        first = not self._shown.endswith(CURSOR)
        if first or self._clock() - self._last >= self.interval:
            await self._show(preview(text, self.limit))

    async def finish(self, final: str) -> bool:
        """Replace the live message with the final first part. False: nothing live, send normally."""
        if not self.live:
            return False
        try:
            await self._edit(self.handle, final)
            return True
        except Exception as exc:
            _LOG.info("Final Discord edit failed (%s); sending the answer as new messages", type(exc).__name__)
            self.broken = True
            return False
