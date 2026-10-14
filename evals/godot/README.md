# Godot 4 static benchmark

Twelve independent GDScript prompts (three per domain: scene/node, typing/signals, physics/input, UI/themes). Each task has a reference example, intentionally incomplete bad example, and mandatory regex criteria. `python -m pytest -q evals/godot/test_godot.py` validates the fixtures and the scorer. These are **static checks** only: they cannot prove GDScript parses, executes, or behaves correctly inside Godot. No Godot editor execution is claimed.
