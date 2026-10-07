def with_archetype_client(html: str) -> str:
    """Add architecture visualization and code-archetype handoff to editor pages."""
    if '/static/code_archetypes.js' in html and '/static/architecture_diagram.js' in html:
        return html
    missing = ''.join(
        tag for tag, marker in (
            ('<script src="/static/architecture_diagram.js" defer></script>', '/static/architecture_diagram.js'),
            ('<script src="/static/code_archetypes.js" defer></script>', '/static/code_archetypes.js'),
        ) if marker not in html
    )
    body_end = html.casefold().rfind('</body>')
    if body_end < 0:
        return html + missing
    return html[:body_end] + missing + html[body_end:]
