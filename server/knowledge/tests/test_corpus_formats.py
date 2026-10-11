from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from starkb.corpus_formats import parse_source
from starkb.corpus_manifest import CorpusError
from starkb.store import embed_input
from corpus_fixture import FIXTURES


@pytest.mark.parametrize("file", ["guide.md", "guide.rst", "Fixture.xml"])
def test_excerpts_preserve_exact_source_lines_and_kind(file):
    raw = (FIXTURES / file).read_bytes()
    result = parse_source(raw, file, "https://example.invalid/source")
    lines = raw.decode().splitlines(keepends=True)
    assert result.doc.chunks and len(result.spans) == len(result.doc.chunks)
    for chunk, span in zip(result.doc.chunks, result.spans):
        assert chunk.text == "".join(lines[span["line_start"] - 1:span["line_end"]])
        assert chunk.kind == "source-" + span["source_kind"]
        assert span["standalone_example_verified"] is False
        assert embed_input(result.doc.title, chunk.heading, chunk.text).endswith(chunk.text)


def test_whole_start_middle_end_are_preserved_in_long_source():
    text = "# Long fixture\nEARLY-CONSTRAINT\n" + "body sentence\n" * 150
    text += "MIDDLE-CORRECTION\n" + "more body\n" * 150 + "FINAL-FAILURE\n"
    result = parse_source(text.encode(), "guide.md", "u")
    assert "".join(c.text for c in result.doc.chunks) == text
    assert "continued source excerpts" in " ".join(result.warnings)


def test_rst_includes_remain_visible_and_are_never_read(tmp_path):
    raw = (FIXTURES / "guide.rst").read_bytes()
    result = parse_source(raw, "guide.rst", "u")
    assert "../../outside-secret.txt" in "".join(c.text for c in result.doc.chunks)
    assert "RST directive retained without execution: include" in result.warnings
    assert not list(tmp_path.iterdir())


def test_mdn_macros_and_mdx_are_explicit_unexpanded_reference():
    raw = b"# Fixture\n{{compat}}\nimport Example from './example.md'\n<Component />\n[!INCLUDE]\n"
    result = parse_source(raw, "guide.mdx", "u")
    assert "".join(c.text for c in result.doc.chunks) == raw.decode()
    assert any("no expansion" in warning for warning in result.warnings)
    assert any("no rendering" in warning for warning in result.warnings)


@pytest.mark.parametrize("raw,path", [
    (b"\xff", "guide.md"), (b"a\0b", "guide.md"), (b"x" * 2000, "guide.md"),
    (b"<!DOCTYPE class [<!ENTITY secret SYSTEM 'file:///outside'>]><class/>", "Fixture.xml"),
    (b"", "guide.rst"),
])
def test_unreadable_or_oversized_content_fails_without_truncation(raw, path):
    with pytest.raises(CorpusError):
        parse_source(raw, path, "u")


def test_no_heading_is_invented_from_code_or_rst_indentation():
    markdown = parse_source(b"# Title\n```python\n# not a heading\n```\n", "a.md", "u")
    assert all(c.heading == "Title" for c in markdown.doc.chunks)
    rst = parse_source(b"Title\n=====\n\n.. code-block:: python\n\n   Code\n   ====\n", "a.rst", "u")
    assert all(c.heading == "Title" for c in rst.doc.chunks)
