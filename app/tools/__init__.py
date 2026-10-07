from app.tools.pages import make_page_tools
from app.tools.relationships import make_relationship_tools
from app.tools.resolve import make_resolve_tools
from app.tools.search import make_search_tools


def make_all_tools(pool) -> list:
    return [
        *make_resolve_tools(pool),
        *make_page_tools(pool),
        *make_relationship_tools(pool),
        *make_search_tools(pool),
    ]


__all__ = [
    "make_all_tools",
    "make_resolve_tools",
    "make_page_tools",
    "make_relationship_tools",
    "make_search_tools",
]
