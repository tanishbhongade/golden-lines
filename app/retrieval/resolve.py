import re

from psycopg_pool import AsyncConnectionPool

TRIGRAM_THRESHOLD = 0.7


def _slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


async def resolve_entity(
        name: str,
        pool: AsyncConnectionPool,
        limit: int = 5,
        trigram_threshold: float = TRIGRAM_THRESHOLD,
) -> list[dict]:
    """
    Resolve a user mention to candidate entities.

    Ladder: exact key → exact alias → prefix → trigram on display_name/alias.
    Returns candidates, never picks a winner.
    """
    name = name.strip()
    if not name:
        return []

    lower = name.lower()
    slug = _slugify(name)
    rung_limit = limit * 2

    results: dict[str, dict] = {}

    def _add(row: dict, match_type: str, score: float) -> None:
        existing = results.get(row["key"])
        if existing is None or score > existing["score"]:
            results[row["key"]] = {
                "key": row["key"],
                "type": row["type"],
                "display_name": row["display_name"],
                "match_type": match_type,
                "score": float(score),
            }

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # 1. exact key
            await cur.execute(
                "SELECT key, type, display_name FROM entities WHERE key = %s",
                (name,),
            )
            for row in await cur.fetchall():
                _add(row, "exact", 1.0)

            # 2. exact alias
            await cur.execute(
                """
                SELECT e.key, e.type, e.display_name
                FROM aliases a
                         JOIN entities e ON e.key = a.entity_key
                WHERE a.alias = %s
                    LIMIT %s
                """,
                (lower, rung_limit),
            )
            for row in await cur.fetchall():
                _add(row, "alias", 1.0)

            # 3. prefix
            if slug:
                await cur.execute(
                    """
                    SELECT key, type, display_name
                    FROM entities
                    WHERE key LIKE %s
                       OR key LIKE %s
                        LIMIT %s
                    """,
                    (f"%/{slug}", f"%/{slug}-%", rung_limit),
                )
                for row in await cur.fetchall():
                    _add(row, "prefix", 0.8)

            # 4. trigram on display_name and alias
            await cur.execute(
                """
                SELECT key, type, display_name, sim
                FROM (
                    SELECT key, type, display_name, similarity(display_name, %s) AS sim
                    FROM entities
                    UNION ALL
                    SELECT e.key, e.type, e.display_name, similarity(a.alias, %s) AS sim
                    FROM aliases a
                    JOIN entities e ON e.key = a.entity_key
                    ) t
                WHERE sim >= %s
                ORDER BY sim DESC
                    LIMIT %s
                """,
                (lower, lower, trigram_threshold, rung_limit),
            )
            for row in await cur.fetchall():
                _add(row, "trigram", row["sim"])

    return sorted(
        results.values(),
        key=lambda r: (-r["score"], r["key"]),
    )[:limit]
