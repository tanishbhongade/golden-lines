from langchain_core.tools import tool

from app.retrieval import resolve as _resolve


def make_resolve_tools(pool):
    @tool
    async def resolve_entity(name: str) -> list[dict]:
        """Resolve a user-mentioned name to candidate entities.

        Returns candidates with key, type, display_name. If exactly one
        candidate is returned, use it. If multiple, pick the one that fits
        the question. If none, say so — do not invent a key."""
        results = await _resolve.resolve_entity(name, pool)
        return [
            {"key": r["key"], "type": r["type"], "display_name": r["display_name"]}
            for r in results
        ]

    return [resolve_entity]
