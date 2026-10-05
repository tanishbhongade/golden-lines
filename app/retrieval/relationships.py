from psycopg_pool import AsyncConnectionPool


async def lines_by(
        speaker_path: str,
        pool: AsyncConnectionPool,
) -> list[dict]:
    """All pages whose `speaker` relationship points at this entity."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT p.path, p.title, p.type
                FROM relationships r
                         JOIN pages p ON p.path = r.source
                WHERE r.relationship = 'speaker'
                  AND r.target = %s
                ORDER BY p.path
                """,
                (speaker_path,),
            )
            return await cur.fetchall()


async def lines_about(
        topic_path: str,
        pool: AsyncConnectionPool,
) -> list[dict]:
    """All pages tagged with this topic."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT p.path, p.title, p.type
                FROM relationships r
                         JOIN pages p ON p.path = r.source
                WHERE r.relationship = 'topics'
                  AND r.target = %s
                ORDER BY p.path
                """,
                (topic_path,),
            )
            return await cur.fetchall()


async def backlinks(
        page_path: str,
        pool: AsyncConnectionPool,
) -> list[dict]:
    """Every page that points at this one, with relationship type."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT r.source, r.relationship, p.title, p.type
                FROM relationships r
                         JOIN pages p ON p.path = r.source
                WHERE r.target = %s
                ORDER BY r.relationship, r.source
                """,
                (page_path,),
            )
            return await cur.fetchall()


async def topics_of(
        page_path: str,
        pool: AsyncConnectionPool,
) -> list[dict]:
    """Topics this page is tagged with."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT r.target AS path, p.title, p.type
                FROM relationships r
                         JOIN pages p ON p.path = r.target
                WHERE r.source = %s
                  AND r.relationship = 'topics'
                ORDER BY r.target
                """,
                (page_path,),
            )
            return await cur.fetchall()


async def get_related(
        page_path: str,
        pool: AsyncConnectionPool,
) -> list[dict]:
    """
    One-hop neighborhood — both directions, all relationship types.
    Returns connected pages with direction and edge type.

    Use when the LLM wants context around a page: 'what's connected to X?'
    More useful than backlinks alone for exploratory queries.
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT 'out'    AS direction,
                       r.relationship,
                       r.target AS path,
                       p.title,
                       p.type
                FROM relationships r
                         JOIN pages p ON p.path = r.target
                WHERE r.source = %s

                UNION ALL

                SELECT 'in'     AS direction,
                       r.relationship,
                       r.source AS path,
                       p.title,
                       p.type
                FROM relationships r
                         JOIN pages p ON p.path = r.source
                WHERE r.target = %s

                ORDER BY direction, relationship, path
                """,
                (page_path, page_path),
            )
            return await cur.fetchall()


async def list_relationship_types(
        pool: AsyncConnectionPool,
) -> list[dict]:
    """
    What edge types exist in the graph and how often each is used.
    Small, cacheable, helps the LLM know what traversals are possible.
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT relationship, COUNT(*) AS count
                FROM relationships
                GROUP BY relationship
                ORDER BY count DESC, relationship
                """
            )
            return await cur.fetchall()
