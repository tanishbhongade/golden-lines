from psycopg_pool import AsyncConnectionPool


async def lines_by(speaker_key: str, pool: AsyncConnectionPool) -> list[dict]:
    """Golden lines whose speaker is this entity."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT g.path, g.title
                FROM relationships r
                         JOIN golden_lines g ON g.path = r.source
                WHERE r.relationship = 'speaker' AND r.target = %s
                ORDER BY g.path
                """,
                (speaker_key,),
            )
            return await cur.fetchall()


async def lines_about(topic_key: str, pool: AsyncConnectionPool) -> list[dict]:
    """Golden lines tagged with this topic."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT g.path, g.title
                FROM relationships r
                         JOIN golden_lines g ON g.path = r.source
                WHERE r.relationship = 'topics' AND r.target = %s
                ORDER BY g.path
                """,
                (topic_key,),
            )
            return await cur.fetchall()


async def get_related(key: str, pool: AsyncConnectionPool) -> list[dict]:
    """
    Neighborhood of a key.
      - Golden line: outbound edges (speaker, topics, source)
      - Entity: inbound edges (golden lines that reference it)
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            if key.startswith("golden-lines/"):
                # outbound
                await cur.execute(
                    """
                    SELECT 'out' AS direction,
                           r.relationship,
                           r.target AS key,
                           e.display_name AS title,
                           e.type
                    FROM relationships r
                        JOIN entities e ON e.key = r.target
                    WHERE r.source = %s
                    ORDER BY r.relationship, r.target
                    """,
                    (key,),
                )
            else:
                # inbound
                await cur.execute(
                    """
                    SELECT 'in' AS direction,
                           r.relationship,
                           r.source AS key,
                           g.title,
                           'golden-line' AS type
                    FROM relationships r
                        JOIN golden_lines g ON g.path = r.source
                    WHERE r.target = %s
                    ORDER BY r.relationship, r.source
                    """,
                    (key,),
                )
            return await cur.fetchall()