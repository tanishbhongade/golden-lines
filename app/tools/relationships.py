from langchain_core.tools import tool

from app.retrieval import relationships as _rel


def make_relationship_tools(pool):
    @tool
    async def lines_by(speaker_path: str) -> list[dict]:
        """All golden lines whose speaker is this entity.

        Returns pointers only (path, title, type) — no content.
        Call get_page on a path to read the line itself.

        Input must be a slug path from resolve_entity.
        """
        return await _rel.lines_by(speaker_path, pool)

    @tool
    async def lines_about(topic_path: str) -> list[dict]:
        """All pages tagged with this topic.
        Input must be a slug path from resolve_entity."""
        return await _rel.lines_about(topic_path, pool)

    @tool
    async def backlinks(page_path: str) -> list[dict]:
        """Every page that references this one, with relationship type."""
        return await _rel.backlinks(page_path, pool)

    @tool
    async def get_related(page_path: str) -> list[dict]:
        """One-hop neighborhood of a page — both directions, all edge types."""
        return await _rel.get_related(page_path, pool)

    return [lines_by, lines_about, backlinks, get_related]
