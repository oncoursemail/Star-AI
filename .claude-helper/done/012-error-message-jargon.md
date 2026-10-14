# Plain-language error messages (backend strings)
Find user-facing error strings in star/ that contain developer instructions (e.g. 'pip install -r requirements-voice.txt', module or env-var names) shown to normal users, and give each a plain-language message with the technical hint moved to logs or an 'Advanced' detail field. Keep tests passing; update tests that assert on exact strings. Don't touch frontend/ (another agent owns UI).
claimed by lane B at 2026-10-14T08:41:34Z
PR: https://github.com/oncoursemail/Star-AI/pull/367 (branch star/helper-012-error-message-jargon)
Result: voice-extras errors (media_features, voice/devices, discord health) now plain-language; pip hint moved to logs. Full pytest: 6701 passed. Discord CLI stderr and env-var strings not changed.
