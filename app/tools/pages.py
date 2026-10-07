from langchain_core.tools import tool

from app.retrieval import pages as _pages


def make_page_tools(pool):
    @tool
    async def get_page(key: str) -> dict | None:
        """Fetch a page by its key.

        Golden lines: returns metadata plus the full line text.
        Entities (person/topic/source): returns metadata plus the list of
        golden lines that reference it under 'referenced_by'.

        Returns None if the key doesn't exist."""
        return await _pages.get_page(key, pool)

    @tool
    async def list_entities(
            type_: str | None = None,
            limit: int = 100,
    ) -> list[dict]:
        """Browse entities. Optionally filter by type:
        'person', 'topic', or 'source'. Returns key, type, display_name."""
        return await _pages.list_entities(pool, type_=type_, limit=limit)

    return [get_page, list_entities]
