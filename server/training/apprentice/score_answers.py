"""Score answers with night school's own automatic checks (run inside the server container, as the night school user).

    cd /opt/star/learning/app/server/night_school
    STAR_NS_HOME=/opt/star/learning /opt/star/learning/venv/bin/python score_answers.py answers-*.jsonl > scored.jsonl

Uses exactly what night school scores with: the pool loader (tasks + unit tests + prelude), the app's
star.eval_checks.score_answer, the knowledge service's Luau check and the sandboxed Luau VM (RealModel.score). No
model is called. Prints one JSON row per answer: {"id", "arm", "passed", "reasons", "infra"}.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> None:
    from nightschool.config import Settings
    from nightschool.pool import load_pool
    from nightschool.real import RealModel, bootstrap
    settings = Settings()
    bootstrap(settings)
    from star import eval_checks as checks
    model = RealModel(settings, None, knowledge=settings.knowledge_url)
    pool = load_pool(settings.pool)
    model.prelude = pool.prelude
    tasks = {t["id"]: t for t in pool.tasks}
    for path in sys.argv[1:]:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            out = {"id": row["id"], "arm": row.get("arm", ""), "passed": False, "reasons": [], "infra": ""}
            task = tasks.get(row["id"])
            if task is None:
                out["infra"] = "task not in pool"
            else:
                try:
                    score = model.score(task, row.get("answer") or "")
                    out["passed"], out["reasons"] = bool(score.passed), [str(r)[:160] for r in score.reasons[:4]]
                except checks.InfraError as exc:
                    out["infra"] = str(exc)[:160]
            print(json.dumps(out), flush=True)
    model.close()


if __name__ == "__main__":
    main()
