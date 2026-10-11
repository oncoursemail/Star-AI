"""Keep a code answer whole inside the reply's length limit.

A STAR Server turn has a fixed number of answer tokens (brain_router: 1600 for a full answer),
and the model writes about ten of them per second. Measured on the stored evaluation answers
(evals/results/baseline-*.json): 12 of 57 answers stopped exactly at that limit, three of them in
the middle of the code. Two things follow from that, and both live here:

  * `continuation` / `splice` (always on): when an answer stops inside a code block, STAR asks once
    more for the missing lines only and joins them on. No model call happens unless the answer was
    really cut; an answer cut in its closing prose only gets an honest one-line note.
  * `SHAPE_RULES` (OFF by default, `STAR_ANSWER_SHAPE=on`): one short per-turn instruction for
    requests that ask for code: the complete code first, brief comments, a short explanation after
    it. It made answers shorter and faster but reproduced two regressions on the evaluation suite
    (see `rule_enabled`), so it ships switched off until a wording passes the gate.

Pure string functions; `star.agent.execute` makes the request.
"""
from __future__ import annotations

import re

SHAPE_HEADING = "ANSWER SHAPE (a rule from STAR)"
SHAPE_RULES = (
    "Your reply has a hard length limit and this request asks for code, so the code must be whole: give the "
    "complete, working code first, one fenced luau block per script or module, with short comments only where "
    "they help (no doc-comment header on every function). After the code add at most five short bullet points: "
    "what it does, where it goes, and what you could not verify. Do not repeat the code in prose, and add a usage "
    "example only if the request asks for one. Every block must run as shown: define what it uses before using "
    "it. Shorter must not mean less: keep every check and every requirement the request lists."
)
# The rule is about code answers. A question that asks for an explanation gets none of it (measured: with the
# rule on every Roblox turn, a documentation question was answered with a script instead of the explanation).
_ASKS_FOR_CODE = re.compile(
    r"\b(?:write|make|create|build|fix|refactor|convert|implement|script|code|add|generate|rewrite|debug)\b|```",
    re.IGNORECASE)
ENV_VAR = "STAR_ANSWER_SHAPE"      # "on" adds the per-turn rule (docs/evals.md: a prompt edit needs a switch)
CONTINUATION_TOKENS = 900          # one extra request of at most this many tokens, twice at most
MAX_CONTINUATIONS = 2
LENGTH_NOTE = "\n\n*(STAR's answer reached its length limit here.)*"
_FENCE_LINE = re.compile(r"^[ \t]*```", re.M)
_OPENER = re.compile(r"^[ \t]*```[^\n]*\n?", re.M)


def rule_enabled(environ=None) -> bool:
    """The per-turn rule is OFF unless STAR_ANSWER_SHAPE is `on`.

    It was measured on suite v2 (docs/agents/eval-gains.md): answers got about a quarter shorter and
    the median turn went from 149 s to 109 s, but two tasks that pass without it failed with it in
    every run (a terser draft that lost a check; a path comment put above `--!strict`). A change
    that reproduces a regression stays off by default, like a skill pack that did (docs/evals.md).
    The continuation is not a prompt edit (it only runs after an answer was cut) and has no switch.
    """
    import os
    return (os.environ if environ is None else environ).get(ENV_VAR, "").strip().lower() == "on"


def asks_for_code(prompt: str) -> bool:
    """Does the request ask for code to be written or changed (the same words the router uses)?"""
    return bool(_ASKS_FOR_CODE.search(prompt or ""))


def stops_inside_code(answer: str) -> bool:
    """True when the text ends inside a fenced block (an odd number of fence lines)."""
    return len(_FENCE_LINE.findall(answer or "")) % 2 == 1


def continuation(answer: str) -> tuple[str, str]:
    """(the part of a cut answer that is kept, the instruction that asks for the rest).

    The last line of an answer that ran into the limit is almost always half a line, so the kept
    part ends with the last complete line and the model is told to write the next one in full.
    """
    kept = answer if answer.endswith("\n") else answer[:answer.rfind("\n") + 1]
    lines = [line for line in kept.splitlines() if line.strip()]
    last = lines[-1].strip() if lines else ""
    cut = answer[len(kept):].strip()
    instruction = (
        "Your answer above was cut off by the length limit in the middle of a code block. Continue it: reply with "
        "only the remaining lines of that same code block in one ```luau fence. "
        + (f"The last complete line was:\n{last[:200]}\n" if last and not last.startswith("```") else "")
        + (f"The next line was cut off after:\n{cut[:200]}\nWrite that line in full first. " if cut else "")
        + "Do not repeat lines that are already written and do not start the code again. Finish the code compactly, "
          "close the fence, then add at most two short sentences."
    )
    return kept, instruction


def _strip_opener(text: str) -> str:
    text = text.lstrip("\n")
    first = text.split("\n", 1)[0]
    return text[len(first) + 1:] if first.strip().startswith("```") and "\n" in text else text


def splice(kept: str, reply: str) -> str:
    """Join the kept part of a cut answer and the model's continuation into one answer.

    Handles the three things a model does when asked to continue: it re-opens the fence, it
    repeats the last line or two, or it starts the whole block again (then its block replaces the
    unfinished one). A continuation that was cut off too leaves the block open: the caller asks
    again, or closes the block and says so.
    """
    if not (reply or "").strip():
        return kept
    opener_at = [m.start() for m in _OPENER.finditer(kept)]
    block_start = opener_at[-1] if opener_at and stops_inside_code(kept) else None
    reply_code = _strip_opener(reply) if reply.lstrip().startswith("```") else reply
    if block_start is not None:
        written = kept[block_start:].split("\n", 1)[1] if "\n" in kept[block_start:] else ""
        head = [line.strip() for line in written.splitlines() if line.strip()][:3]
        again = [line.strip() for line in reply_code.splitlines() if line.strip()][:3]
        if len(head) >= 2 and head[:2] == again[:2]:
            # The model wrote the block again from its first line: keep its version.
            opener = kept[block_start:].split("\n", 1)[0]
            return kept[:block_start] + opener + "\n" + reply_code
    kept_lines = kept.splitlines()
    new_lines = reply_code.splitlines()
    overlap = 0
    for size in range(min(6, len(kept_lines), len(new_lines)), 0, -1):
        if [l.strip() for l in kept_lines[-size:]] == [l.strip() for l in new_lines[:size]] and any(
                l.strip() for l in new_lines[:size]):
            overlap = size
            break
    return kept + "\n".join(new_lines[overlap:]) + ("\n" if reply_code.endswith("\n") else "")
