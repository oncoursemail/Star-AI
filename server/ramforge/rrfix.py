"""rrfix.py OUT N : capture the exact rerank inputs starkb sends (hybrid candidates, 15 docs) for the first N eval questions."""
import json, sys, os
from pathlib import Path
sys.path.insert(0, "/opt/star/knowledge/app")
from starkb.search import Searcher
from starkb.evaluate import load_questions
qs = load_questions(Path("/opt/star/knowledge/app/eval/questions.jsonl"))[: int(sys.argv[2])]
s = Searcher(Path("/opt/star/knowledge/data/kb.sqlite3"), reuse_query_vectors=True)
cap = []
def fake(q, docs, top_n=None):
    cap.append({"query": q, "docs": docs}); return [(i, -float(i)) for i in range(len(docs))]
s.brain.rerank = fake
for q in qs:
    s.search(q["question"], mode="hybrid+rerank", top=10, per_doc=2, rerank_n=15)
json.dump(cap, open(sys.argv[1], "w"))
print(len(cap), "queries,", sum(len(c["docs"]) for c in cap), "docs, mean chars", sum(len(d) for c in cap for d in c["docs"]) // sum(len(c["docs"]) for c in cap))
