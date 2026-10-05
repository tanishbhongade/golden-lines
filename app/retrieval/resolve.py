import re

from psycopg_pool import AsyncConnectionPool

# GBrain uses 0.7 for "high-specificity" fuzzy matching. Lower thresholds
# (0.3-ish) match too many unrelated things — "aliceberg" would match "alice".
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
    Resolve a user-supplied mention to candidate pages.

    Deterministic ladder — every rung contributes candidates, results are
    deduped by path with the strongest match_type kept:

      1. exact path match             ("people/chaitanya-patil")
      2. exact alias match            ("cp" → people/chaitanya-patil)
      3. prefix expansion             ("chaitanya" → people/chaitanya-patil)
      4. trigram >= threshold         ("chaitnya patil", "chaitanya patl")
      5. slugify fallback             ("Chaitanya Patil" → people/chaitanya-patil)

    Returns candidates with: path, title, type, match_type, score.
    The caller (LLM or human) makes the final pick — this function never
    silently chooses.
    """
    name = name.strip()
    if not name:
        return []

    lower = name.lower()
    slug = _slugify(name)
    rung_limit = limit * 2

    results: dict[str, dict] = {}

    def _add(row: dict, match_type: str, score: float) -> None:
        # Keep the highest-scoring match for any given path
        existing = results.get(row["path"])
        if existing is None or score > existing["score"]:
            results[row["path"]] = {
                "path": row["path"],
                "title": row["title"],
                "type": row["type"],
                "match_type": match_type,
                "score": float(score),
            }

    async with pool.connection() as conn:
        async with conn.cursor() as cur:

            # 1. exact path
            await cur.execute(
                "SELECT path, title, type FROM pages WHERE path = %s",
                (name,),
            )
            for row in await cur.fetchall():
                _add(row, "exact", 1.0)

            # 2. exact alias (lowercase match)
            await cur.execute(
                """
                SELECT p.path, p.title, p.type
                FROM aliases a
                         JOIN pages p ON p.path = a.page_path
                WHERE a.alias = %s
                    LIMIT %s
                """,
                (lower, rung_limit),
            )
            for row in await cur.fetchall():
                _add(row, "alias", 1.0)

            # 3. prefix expansion — path ends with /<slug> or /<slug>-...
            if slug:
                await cur.execute(
                    """
                    SELECT path, title, type
                    FROM pages
                    WHERE path LIKE %s
                       OR path LIKE %s
                        LIMIT %s
                    """,
                    (f"%/{slug}", f"%/{slug}-%", rung_limit),
                )
                for row in await cur.fetchall():
                    _add(row, "prefix", 0.8)

            # 4. trigram — either title or any alias above threshold
            await cur.execute(
                """
                SELECT path, title, type, sim
                FROM (SELECT path,
                             title,
                             type,
                             similarity(title, %s) AS sim
                      FROM pages
                      UNION ALL
                      SELECT p.path,
                             p.title,
                             p.type,
                             similarity(a.alias, %s) AS sim
                      FROM aliases a
                               JOIN pages p ON p.path = a.page_path) t
                WHERE sim >= %s
                ORDER BY sim DESC
                    LIMIT %s
                """,
                (lower, lower, trigram_threshold, rung_limit),
            )
            for row in await cur.fetchall():
                _add(row, "trigram", row["sim"])

            # 5. slugify fallback — catches "Chaitanya Patil" → people/chaitanya-patil
            if slug:
                await cur.execute(
                    "SELECT path, title, type FROM pages WHERE path LIKE %s LIMIT %s",
                    (f"%/{slug}", rung_limit),
                )
                for row in await cur.fetchall():
                    _add(row, "slugify", 0.5)

    return sorted(
        results.values(),
        key=lambda r: (-r["score"], r["path"]),
    )[:limit]
