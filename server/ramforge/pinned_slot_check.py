"""Issue 118 check for server/ramforge/patches/0002: client A streams an answer on slot S; client B sends a
1-token cache warm-up (like STAR's post-answer warm-up or prefill draft) pinned to the same slot while A generates.
On llama.cpp builds before upstream #30295 the server loads B's cached prompt INTO the busy slot, and A's
answer continues on the wrong context. Exit code 1 when that happens. Prints only texts and a verdict, never the key.
Run on a quiet server: it sends 7 short requests (about 2 minutes on star-voice)."""
import json, sys, threading, time
from pathlib import Path
import httpx

if len(sys.argv) < 2:
    sys.exit("usage: pinned_slot_check.py BASE_URL [MODEL] [SLOT] [N_TOKENS]   (key: ~/.star/server_api_key if present)")
BASE = sys.argv[1].rstrip("/")
MODEL = sys.argv[2] if len(sys.argv) > 2 else "star-voice"
SLOT = int(sys.argv[3]) if len(sys.argv) > 3 else 0
N = int(sys.argv[4]) if len(sys.argv) > 4 else 120
_key = Path.home() / ".star" / "server_api_key"
H = {"Authorization": f"Bearer {_key.read_text().strip()}"} if _key.is_file() else {}
STORY = "Once upon a time a dragon named Ember guarded a golden key in a deep cave under the northern hills. " * 10
BREAD = "Here is a careful step by step recipe for baking a simple loaf of white bread at home. Step 1:"


def post(prompt, n, slot):
    r = httpx.post(BASE + "/completion", headers=H, timeout=600, json={
        "model": MODEL, "prompt": prompt, "id_slot": slot, "n_predict": n, "temperature": 0.0,
        "cache_prompt": True})
    r.raise_for_status()
    return r.json()


def stream(prompt, n, slot, on_first=None):
    out, first = [], True
    with httpx.stream("POST", BASE + "/completion", headers=H, timeout=600, json={
            "model": MODEL, "prompt": prompt, "id_slot": slot, "n_predict": n, "temperature": 0.0,
            "ignore_eos": True, "stream": True, "cache_prompt": True}) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            chunk = json.loads(line[6:])
            out.append(chunk.get("content", ""))
            if first and chunk.get("content"):
                first = False
                if on_first:
                    on_first()
            if chunk.get("stop"):
                break
    return "".join(out)


def run(pin_busy):
    post(STORY, 4, SLOT)                    # slot holds the story; the bread prompt below pushes it to the RAM cache
    warm = {}

    def fire():
        def go():
            t = time.time()
            warm["res"] = post(STORY + " The dragon", 1, SLOT)   # the other client's warm-up, pinned to the busy slot
            warm["s"] = round(time.time() - t, 1)
        th = threading.Thread(target=go, daemon=True)
        th.start()
        warm["th"] = th
        time.sleep(0.5)

    text = stream(BREAD, N, SLOT, on_first=fire if pin_busy else None)
    if "th" in warm:
        warm["th"].join(600)
    return text, warm.get("s")


if __name__ == "__main__":
    a, _ = run(False)
    b, _ = run(False)
    c, waited = run(True)
    print("MODEL", MODEL, "slot", SLOT, "n", N)
    print("baseline twice identical:", a == b)
    print("with pinned warm-up identical to baseline:", c == a, "(warm-up returned after", waited, "s)")
    if c != a:
        i = next((k for k in range(min(len(a), len(c))) if a[k] != c[k]), min(len(a), len(c)))
        print("diverges at char", i)
        print("--- baseline tail:", repr(a[max(0, i - 80):i + 200]))
        print("--- pinned   tail:", repr(c[max(0, i - 80):i + 200]))
    sys.exit(0 if c == a else 1)
