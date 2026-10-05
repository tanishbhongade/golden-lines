from psycopg_pool import AsyncConnectionPool


class RelationalStore:
    """Relational projection: pages + relationships."""

    def __init__(self, pool: AsyncConnectionPool):
        self._pool = pool

    # ----- pages -----

    async def upsert_page(
            self,
            path: str,
            title: str,
            type_: str,
            hash_: str,
            version: str,
    ) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO pages (path, title, type, hash, version, updated_at)
                    VALUES (%s, %s, %s, %s, %s, NOW()) ON CONFLICT (path) DO
                    UPDATE SET
                        title = EXCLUDED.title,
                        type = EXCLUDED.type,
                        hash = EXCLUDED.hash,
                        version = EXCLUDED.version,
                        updated_at = NOW()
                    """,
                    (path, title, type_, hash_, version),
                )

    async def get_page(self, path: str) -> dict | None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM pages WHERE path = %s", (path,)
                )
                return await cur.fetchone()

    async def list_pages(self, type_: str | None = None) -> list[dict]:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                if type_ is None:
                    await cur.execute(
                        "SELECT * FROM pages ORDER BY path"
                    )
                else:
                    await cur.execute(
                        "SELECT * FROM pages WHERE type = %s ORDER BY path",
                        (type_,),
                    )
                return await cur.fetchall()

    async def delete_page(self, path: str) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM pages WHERE path = %s", (path,))

    # ----- relationships -----

    async def upsert_relationship(
            self, source: str, relationship: str, target: str
    ) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO relationships (source, relationship, target)
                    VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
                    """,
                    (source, relationship, target),
                )

    async def get_relationships(
            self,
            source: str | None = None,
            target: str | None = None,
            relationship: str | None = None,
    ) -> list[dict]:
        clauses, params = [], []
        if source is not None:
            clauses.append("source = %s");
            params.append(source)
        if target is not None:
            clauses.append("target = %s");
            params.append(target)
        if relationship is not None:
            clauses.append("relationship = %s");
            params.append(relationship)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    SELECT source, relationship, target
                    FROM relationships
                    {where}
                    """,
                    params,
                )
                return await cur.fetchall()

    async def delete_relationships_from(self, source: str) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM relationships WHERE source = %s", (source,)
                )
