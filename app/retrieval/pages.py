from psycopg_pool import AsyncConnectionPool


async def get_page(key: str, pool: AsyncConnectionPool) -> dict | None:
    """
    Fetch a page. Golden lines and entities are unified here —
    dispatches on whether the key exists in golden_lines first.
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # try golden line first
            await cur.execute(
                """
                SELECT path, title, body, hash, version, updated_at
                FROM golden_lines
                WHERE path = %s
                """,
                (key,),
            )
            line = await cur.fetchone()
            if line is not None:
                await cur.execute(
                    """
                    SELECT id, content, metadata
                    FROM chunks
                    WHERE line_path = %s
                    ORDER BY id
                    """,
                    (key,),
                )
                chunks = await cur.fetchall()
                line["type"] = "golden-line"
                line["chunks"] = chunks
                line["content"] = line["body"] or "\n\n".join(
                    c["content"] for c in chunks
                )
                return line

            # fall back to entity
            await cur.execute(
                """
                SELECT key, type, display_name, metadata
                FROM entities
                WHERE key = %s
                """,
                (key,),
            )
            entity = await cur.fetchone()
            if entity is None:
                return None

            await cur.execute(
                """
                SELECT r.relationship, r.source AS path, g.title
                FROM relationships r
                         JOIN golden_lines g ON g.path = r.source
                WHERE r.target = %s
                ORDER BY r.relationship, r.source
                """,
                (key,),
            )
            entity["referenced_by"] = await cur.fetchall()
            return entity


async def list_entities(
        pool: AsyncConnectionPool,
        type_: str | None = None,
        limit: int = 100,
) -> list[dict]:
    """Browse entities, optionally filtered by type."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            if type_ is not None:
                await cur.execute(
                    """
                    SELECT key, type, display_name
                    FROM entities
                    WHERE type = %s
                    ORDER BY key
                        LIMIT %s
                    """,
                    (type_, limit),
                )
            else:
                await cur.execute(
                    """
                    SELECT key, type, display_name
                    FROM entities
                    ORDER BY type, key
                        LIMIT %s
                    """,
                    (limit,),
                )
            return await cur.fetchall()
