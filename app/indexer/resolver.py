import re

from psycopg import AsyncCursor

TRIGRAM_THRESHOLD = 0.85


def _display_name(key: str) -> str:
    name = key.split("/", 1)[-1]
    name = re.sub(r"[-_]+", " ", name)
    return name.title()


def _entity_type(key: str) -> str:
    prefix = key.split("/", 1)[0] if "/" in key else "unknown"
    return {
        "people": "person",
        "topics": "topic",
        "sources": "source",
    }.get(prefix, "unknown")


async def resolve_slug(
        cur: AsyncCursor,
        slug: str,
        auto_alias_threshold: float = TRIGRAM_THRESHOLD,
) -> tuple[str, str]:
    """
    Resolve a reference slug to a canonical entity key.
    Returns (canonical_key, resolution) where resolution is one of:
      'exact' | 'alias' | 'auto-alias' | 'new'

    Creates the entity or an alias row as needed. Runs inside the caller's
    transaction — all queries use the provided cursor.
    """
    # 1. exact
    await cur.execute("SELECT 1 FROM entities WHERE key = %s", (slug,))
    if await cur.fetchone():
        return slug, "exact"

    # 2. alias
    await cur.execute(
        "SELECT entity_key FROM aliases WHERE alias = %s", (slug,)
    )
    row = await cur.fetchone()
    if row:
        return row["entity_key"], "alias"

    # 3. trigram — high-specificity match against existing entity keys
    await cur.execute(
        """
        SELECT key, similarity(key, %s) AS score
        FROM entities
        WHERE similarity(key
            , %s) >= %s
        ORDER BY score DESC
            LIMIT 1
        """,
        (slug, slug, auto_alias_threshold),
    )
    row = await cur.fetchone()
    if row:
        await cur.execute(
            """
            INSERT INTO aliases (entity_key, alias)
            VALUES (%s, %s) ON CONFLICT DO NOTHING
            """,
            (row["key"], slug),
        )
        return row["key"], "auto-alias"

    # 4. new entity
    await cur.execute(
        """
        INSERT INTO entities (key, type, display_name)
        VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
        """,
        (slug, _entity_type(slug), _display_name(slug)),
    )
    return slug, "new"
