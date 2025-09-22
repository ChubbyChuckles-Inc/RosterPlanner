from gui.services.html_sanitizer import sanitize_html


def test_sanitize_removes_script_and_on_attributes():
    html = '<div><script>alert(1)</script><a href="javascript:doBad()" onclick="bad()" style="color:red">Link</a></div>'
    out = sanitize_html(html)
    assert "script" not in out
    assert "onclick" not in out
    assert "javascript:doBad" not in out
    assert "style=" not in out


def test_sanitize_keeps_safe_content():
    html = '<div><p>Safe text</p><a href="http://example.com">OK</a></div>'
    out = sanitize_html(html)
    assert "Safe text" in out
    assert "http://example.com" in out
