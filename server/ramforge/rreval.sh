cd /opt/star/knowledge/app
# rreval.sh : starkb eval on the 3 question sets, rerank_n 15 / 8 / 5 (results/kbeval-*.json). Note: the deployed evaluate.py
# may ignore the quiet lock; never run it inside a timing window.
for qf in questions heldout golden-task-queries; do
  for n in 15 8 5; do
    modes="hybrid+rerank"; [ $n = 15 ] && modes="vector,hybrid,hybrid+rerank"
    env STAR_KB_HOME=/opt/star/knowledge STAR_EMBED_MODEL=star-embed-ft1 /opt/star/knowledge/venv/bin/python -m starkb eval \
      --questions eval/$qf.jsonl --modes "$modes" --rerank-n $n --out /opt/star/src/ramforge/results/kbeval-$qf-rr$n.json > /dev/null 2>> /opt/star/src/ramforge/results/kbeval.err
    echo "$(date -u +%T) done $qf rr$n" >> /opt/star/src/ramforge/results/kbeval.progress
  done
done
echo ALLDONE >> /opt/star/src/ramforge/results/kbeval.progress
