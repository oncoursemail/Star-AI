# pr142-fix resume
Branch star/pr142-fix-20261012 (worktree worktrees/wt-pr142-fix), from PR 142 head + merge of origin/star/next 639f2f5.
Done: conflicts in types.ts, desktop_core.py, react_shell.py resolved (both sides kept, allow_cgnat added to each list);
allow_cgnat passed in model_health.probe_server, voice/brain.server_connection, doc_knowledge.knowledge_endpoint_for;
explicit knowledge_endpoint and brain_benchmark stay strict; help text reworded; tests/test_cgnat_callers.py added.
Tests: pytest 4240 passed, 4 known PowerShell failures; tsc clean; vitest 328 passed; vite build ok.
