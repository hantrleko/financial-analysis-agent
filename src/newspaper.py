import html
import re


def inline_markdown(text):
    """
    Safely render a limited subset of inline Markdown to HTML.
    User text is escaped first, then markdown markers are converted.
    """
    safe = html.escape(text, quote=False)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"\*(.+?)\*", r"<i>\1</i>", safe)
    safe = re.sub(r"__(.+?)__", r"<b>\1</b>", safe)
    safe = re.sub(r"_(.+?)_", r"<i>\1</i>", safe)
    safe = re.sub(r"`(.+?)`", r"<code>\1</code>", safe)
    safe = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", safe)
    return safe
