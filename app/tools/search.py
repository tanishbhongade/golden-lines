from langchain_core.tools import tool

from app.retrieval import search as _search


def _with_chunk_note(results: list[dict]) -> dict:
    """
    Wrap search results with a note when any row is a fragment of a longer line.
    Silently a no-op for 1:1 chunking (chunk_count == 1 for every row).
    """
    payload: dict = {"results": results}
    if any(r.get("chunk_count", 1) > 1 for r in results):
        payload["note"] = (
            "Some results are fragments of longer golden lines. "
            "Call get_page on the line_path to read the full text before quoting."
        )
    return payload


def make_search_tools(pool):
    @tool
    async def semantic_search(query: str, limit: int = 5) -> dict:
        """Find content semantically similar to a query.

        Use for conceptual questions: "what do I think about X?",
        "find anything about Y".

        Returns {'results': [...]} where each row has line_path, chunk_index,
        chunk_count, content, metadata, and score. When chunk_count > 1, the
        row is a fragment — call get_page on line_path to read the full line."""
        results = await _search.semantic_search(query, pool, limit=limit)
        return _with_chunk_note(results)

    @tool
    async def hybrid_search(
            query: str,
            speaker: str | None = None,
            topic: str | None = None,
            limit: int = 5,
    ) -> dict:
        """Semantic search filtered by the knowledge graph.

        Use when the user asks about content by a specific person or on a
        specific topic. speaker and topic are entity keys from resolve_entity.

        Returns {'results': [...]} where each row has line_path, chunk_index,
        chunk_count, content, metadata, and score. When chunk_count > 1, the
        row is a fragment — call get_page on line_path to read the full line."""
        results = await _search.hybrid_search(
            query, pool, speaker=speaker, topic=topic, limit=limit,
        )
        return _with_chunk_note(results)

    return [semantic_search, hybrid_search]
