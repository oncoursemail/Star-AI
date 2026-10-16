# Agent Commons (#424) - first slice

Done: `star/acp_adapter.py` - opt-in (`enabled=True` required) ACP client over stdio. Advertises no fs/terminal
capability, rejects agent permission requests unless the host passes `approve`, keeps tool calls as
`agent_reported` receipts, states ok/unavailable/auth_required/timeout/cancelled/error. Tested with a fake
agent (simulation) in `tests/test_acp_adapter.py`. No settings/UI wiring yet.

Left: stream() and tool-approval UI, real OpenCode/Gemini/goose runs on authorized hardware, JSON-RPC (Pi) variant,
mission/event stream into chat, host-verified evidence, sandbox grants, resource admission, React inspector,
benchmarks (gates 2-4).
