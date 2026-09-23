"""Standard Markdown rendering for the optional Workbench render mode."""

from markdown_it import MarkdownIt


_MARKDOWN = MarkdownIt("commonmark", {"html": False})


def render_markdown(content: str) -> str:
    """Render CommonMark while treating embedded HTML as untrusted text."""

    return _MARKDOWN.render(content)
