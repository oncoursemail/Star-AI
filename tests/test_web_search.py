"""Web snippets are capped, URL-filtered, and non-executable."""
from star.web_search import _safe_results, source_context

def test_web_sources_require_ordinary_https_without_credentials():
    items=[
        {"url":"http://example.com","title":"HTTP","description":"not allowed"},
        {"url":"https://u:pw@example.com","title":"Secret","description":"not allowed"},
        {"url":"file:///etc/passwd","title":"Local","description":"not allowed"},
        {"url":"https://example.com/article","title":"OK","description":"Excerpt"},
        {"url":"https://example.com/article","title":"Duplicate","description":"Duplicate"},
    ]
    result=_safe_results(items,text_field="description",limit=5)
    assert len(result)==1 and result[0]["title"]=="OK"
    text=source_context(result)
    assert "https://example.com/article" in text
    assert "untrusted" in text
    assert "entire articles" in text

def test_result_lengths_and_maximum():
    items=[{"url":f"https://example.com/{i}","title":"t"*900,"description":"x"*5000} for i in range(12)]
    records=_safe_results(items,text_field="description",limit=3)
    assert len(records)==3
    assert all(len(r["title"])<=160 and len(r["snippet"])<=1050 for r in records)
