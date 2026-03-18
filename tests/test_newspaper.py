from src.newspaper import inline_markdown


def test_inline_markdown_escapes_html():
    rendered = inline_markdown("hello <script>alert(1)</script>")
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_inline_markdown_keeps_allowed_formatting():
    rendered = inline_markdown("**bold** and *italic* and `code`")
    assert "<b>bold</b>" in rendered
    assert "<i>italic</i>" in rendered
    assert "<code>code</code>" in rendered
