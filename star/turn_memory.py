"""What STAR remembers about a conversation between turns so the server can reuse its prompt.

Two things, both in process memory only (nothing is written to disk, nothing is
a secret, and a restart simply starts again):

1. Sticky tools. The Qwen chat template writes the tool list at the very start
   of the prompt, before the rules and the conversation. STAR picks tools per
   message ("skill" attaches the skill tools, "obsidian" the vault tools, ...),
   so a different message used to mean a different start and the server read
   the rules and the whole conversation again. `TurnMemory` makes the selection
   grow-only inside one conversation:

     * a tool that was attached stays attached on later turns;
     * the order is the order of first attachment, new tools go to the end;
     * each definition is the same Python object content every turn, so its
       JSON is byte-identical.

   It never widens a permission. Earlier *prompts* are remembered, not earlier
   tools, and every turn asks each tool source again what those prompts select
   under the settings of that moment. A source the owner switched off, a
   revoked recipe or a removed vault therefore drops out at once.

2. The shape of the last request (model, tool list, guidance). The post-answer
   warm-up uses it to prime the request the next message will most likely send,
   instead of always priming plain chat (which, on one slot, would replace a
   cached tool prompt).
"""
from __future__ import annotations

_CONVERSATIONS: dict[str, "TurnMemory"] = {}
_MAX_CONVERSATIONS = 32


def _name(definition: dict) -> str:
    return str((definition.get("function") or {}).get("name") or definition.get("name") or "")


class TurnMemory:
    def __init__(self, *, sticky: bool = False):
        self.sticky = sticky
        self.prompts: list[str] = []     # earlier prompts that brought a tool in
        self.order: list[str] = []       # tool names, in the order they were first attached
        self.shape: dict | None = None   # the last request: {'model', 'tools', 'guidance'}

    def choose(self, select, prompt: str) -> list[dict]:
        """This turn's tools from one source: what `prompt` selects plus what earlier prompts did.

        `select(text)` is the source's own selection for one prompt under the current settings.
        """
        if not self.sticky:
            return list(select(prompt))
        chosen: list[dict] = []
        seen: set[str] = set()
        for text in (prompt, *self.prompts):
            for tool in select(text):
                if tool["name"] not in seen:
                    seen.add(tool["name"])
                    chosen.append(tool)
        return chosen

    def arrange(self, definitions: list[dict], prompt: str) -> list[dict]:
        """Put the whole tool list in first-attachment order and remember what is new."""
        if not self.sticky:
            return definitions
        place = {name: index for index, name in enumerate(self.order)}
        known = sorted((item for item in definitions if _name(item) in place), key=lambda item: place[_name(item)])
        new = [item for item in definitions if _name(item) not in place]
        if new:
            self.order.extend(_name(item) for item in new)
            if prompt not in self.prompts:
                self.prompts.append(prompt)
        return known + new

    def remember_request(self, *, model: str, tools: list[dict] | None, guidance: str = "") -> None:
        self.shape = {"model": model, "tools": list(tools) if tools else None, "guidance": guidance}


def for_conversation(scope: str, *, sticky: bool = False) -> TurnMemory:
    """The memory of one conversation (created on first use). `sticky` follows the provider."""
    memory = _CONVERSATIONS.pop(scope, None) or TurnMemory()
    memory.sticky = bool(sticky)
    _CONVERSATIONS[scope] = memory           # newest last
    while len(_CONVERSATIONS) > _MAX_CONVERSATIONS:
        del _CONVERSATIONS[next(iter(_CONVERSATIONS))]
    return memory


def last_shape(scope: str) -> dict | None:
    """The last request of a conversation in this process, or None. Never creates an entry."""
    memory = _CONVERSATIONS.get(scope)
    return memory.shape if memory else None


def forget(scope: str = "") -> None:
    if scope:
        _CONVERSATIONS.pop(scope, None)
    else:
        _CONVERSATIONS.clear()
