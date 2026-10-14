"""Building and reading the Luau test script (same wire format as the evaluation harness)."""
from __future__ import annotations

from dataclasses import dataclass, field

_PROLOGUE_END = "-- ===== test body ====="


def long_bracket(text: str) -> tuple[str, str]:
    level = 0
    while f"]{'=' * level}]" in text:
        level += 1
    return f"[{'=' * level}[", f"]{'=' * level}]"


def build_test_script(prelude: str, answer_code: str, test_body: str) -> str:
    """One Luau file: the answer as a string, the harness prelude, then the task's test body.
    The answer is only ever loaded with `loadstring` into a whitelisted environment (see the prelude)."""
    opener, closer = long_bracket(answer_code)
    return (f"local __SRC = {opener}\n{answer_code}\n{closer}\n{prelude}\n{_PROLOGUE_END}\n"
            f"local __ok, __err = xpcall(function()\n{test_body}\nend, function(e) return tostring(e) end)\n"
            "if not __ok then print('@@ERR\\t' .. string.sub(tostring(__err), 1, 300)) end\n"
            "print('@@DONE')\n")


@dataclass
class Outcome:
    results: list[tuple[str, bool]] = field(default_factory=list)
    load_error: str = ""
    error: str = ""
    done: bool = False

    @property
    def passed(self) -> int:
        return sum(1 for _, ok in self.results if ok)

    @property
    def failed(self) -> int:
        return sum(1 for _, ok in self.results if not ok)

    def all_pass(self, minimum: int) -> bool:
        return (self.done and not self.error and not self.load_error and len(self.results) >= minimum
                and self.failed == 0)


def parse_output(stdout: str) -> Outcome:
    out = Outcome()
    for line in stdout.splitlines():
        if not line.startswith("@@"):
            continue
        parts = line.split("\t", 2)
        tag = parts[0]
        if tag == "@@T" and len(parts) == 3:
            out.results.append((parts[2][:120], parts[1] == "pass"))
        elif tag == "@@LOADERR":
            out.load_error = (parts[1] if len(parts) > 1 else "")[:300]
        elif tag == "@@ERR":
            out.error = (parts[1] if len(parts) > 1 else "")[:300]
        elif tag == "@@DONE":
            out.done = True
    return out
