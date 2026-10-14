"""The CI shard split never loses or duplicates a test, and is the same on every machine."""
from types import SimpleNamespace

import pytest

from tests.sharding import assign_files, parse_shard, split_items


def items(spec):
    return [SimpleNamespace(nodeid=f"tests/{name}.py::t{i}") for name, count in spec for i in range(count)]


@pytest.mark.parametrize("total", [1, 2, 3, 5])
def test_shards_partition_the_suite_exactly(total):
    suite = items([("a", 40), ("b", 3), ("c", 17), ("d", 17), ("e", 1), ("f", 9), ("g", 25)])
    seen = []
    for index in range(1, total + 1):
        kept, dropped = split_items(suite, f"{index}/{total}")
        assert len(kept) + len(dropped) == len(suite)
        assert kept == [item for item in suite if item in kept]  # collection order kept
        seen.extend(item.nodeid for item in kept)
    assert sorted(seen) == sorted(item.nodeid for item in suite)  # each test exactly once


def test_files_are_never_split_and_the_split_is_balanced_and_stable():
    counts = {"tests/a.py": 40, "tests/b.py": 3, "tests/c.py": 17, "tests/d.py": 17, "tests/g.py": 25}
    placed = assign_files(counts, 3)
    assert placed == assign_files(dict(reversed(list(counts.items()))), 3)  # input order is irrelevant
    loads = [sum(n for path, n in counts.items() if placed[path] == shard) for shard in (1, 2, 3)]
    assert loads == [40, 28, 34]  # largest first onto the least-loaded shard
    suite = items([("a", 4), ("b", 2), ("c", 2)])
    for index in (1, 2):
        kept, _ = split_items(suite, f"{index}/2")
        for item in suite:
            same_file = [other for other in suite if other.nodeid.split("::")[0] == item.nodeid.split("::")[0]]
            assert all((other in kept) == (item in kept) for other in same_file)


@pytest.mark.parametrize("spec", ["", "0/3", "4/3", "1/0", "a/b", "1-3", "1/3/5"])
def test_malformed_shard_spec_is_refused(spec):
    with pytest.raises(ValueError):
        parse_shard(spec)
