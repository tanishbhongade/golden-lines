from langchain_core.tools import tool

from app.retrieval import search as _search


def make_search_tools(pool):
    @tool
    async def semantic_search(query: str, limit: int = 5) -> list[dict]:
        """Find chunks semantically similar to the query.
        Returns page_path, content, metadata, score (higher is better)."""
        return await _search.semantic_search(query, pool, limit=limit)

    @tool
    async def hybrid_search(
            query: str,
            speaker: str | None = None,
            topic: str | None = None,
            limit: int = 5,
    ) -> list[dict]:
        """Semantic search filtered by the knowledge graph.
        speaker and topic are slug paths from resolve_entity.
        Use when the user asks about content by a specific person or on a specific topic."""
        return await _search.hybrid_search(
            query, pool, speaker=speaker, topic=topic, limit=limit,
        )

    return [semantic_search, hybrid_search]