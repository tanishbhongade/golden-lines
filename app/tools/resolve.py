from langchain_core.tools import tool

from app.retrieval import resolve as _resolve


def make_resolve_tools(pool):
    @tool
    async def resolve_entity(name: str) -> list[dict]:
        """Resolve a user-mentioned name to candidate pages.

        Returns candidate pages (path, title, type). If exactly one candidate
        is returned, use it. If multiple, pick from context or ask. If none,
        tell the user.
        """
        results = await _resolve.resolve_entity(name, pool)
        return [
            {"path": r["path"], "title": r["title"], "type": r["type"]}
            for r in results
        ]

    return [resolve_entity]
