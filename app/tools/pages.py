from langchain_core.tools import tool

from app.retrieval import pages as _pages


def make_page_tools(pool):
    @tool
    async def get_page(page_path: str) -> dict | None:
        """Fetch a page by its slug path (e.g. 'golden-lines/systems-over-goals').
        Returns metadata plus full concatenated content, or None if not found."""
        return await _pages.get_page(page_path, pool)

    @tool
    async def list_entities(
            type_: str | None = None,
            limit: int = 100,
    ) -> list[dict]:
        """Browse pages. Optionally filter by type: 'golden-line', 'person',
        'topic', or 'source'. Returns path, title, type for each."""
        return await _pages.list_entities(pool, type_=type_, limit=limit)

    return [get_page, list_entities]