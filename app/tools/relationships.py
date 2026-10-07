from langchain_core.tools import tool

from app.retrieval import relationships as _rel


def make_relationship_tools(pool):
    @tool
    async def lines_by(speaker_key: str) -> dict:
        """Golden lines whose speaker is this entity.

        Input must be an entity key from resolve_entity (e.g. 'people/foo').

        Returns pointers only (path, title) — no content. Call get_page on a
        returned path to read the line itself."""
        pointers = await _rel.lines_by(speaker_key, pool)
        return {
            "lines": pointers,
            "note": "Pointers only. Call get_page on each path to read the actual text.",
        }

    @tool
    async def lines_about(topic_key: str) -> dict:
        """Golden lines tagged with this topic.

        Input must be an entity key from resolve_entity (e.g. 'topics/foo').

        Returns pointers only (path, title) — no content. Call get_page to read."""
        pointers = await _rel.lines_about(topic_key, pool)
        return {
            "lines": pointers,
            "note": "Pointers only. Call get_page on each path to read the actual text.",
        }

    @tool
    async def get_related(key: str) -> dict:
        """One-hop neighborhood of a key.

        For a golden line: outbound relationships (speaker, topics, source).
        For an entity: inbound golden lines that reference it.

        Returns pointers only (key, title, type). Call get_page to read content."""
        related = await _rel.get_related(key, pool)
        return {
            "related": related,
            "note": "Pointers only. Call get_page on each key to read the actual content.",
        }

    return [lines_by, lines_about, get_related]
