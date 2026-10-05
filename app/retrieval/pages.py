from psycopg_pool import AsyncConnectionPool


async def get_page(
        page_path: str,
        pool: AsyncConnectionPool,
) -> dict | None:
    """
    Full page: metadata + all chunks concatenated into content.
    Returns None if the path doesn't exist.
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT path, title, type, hash, version, updated_at
                FROM pages
                WHERE path = %s
                """,
                (page_path,),
            )
            page = await cur.fetchone()
            if page is None:
                return None

            await cur.execute(
                """
                SELECT id, content, metadata
                FROM chunks
                WHERE page_path = %s
                ORDER BY id
                """,
                (page_path,),
            )
            chunks = await cur.fetchall()

    page["chunks"] = chunks
    page["content"] = "\n\n".join(c["content"] for c in chunks)
    return page


async def list_entities(
        pool: AsyncConnectionPool,
        type_: str | None = None,
        limit: int = 100,
) -> list[dict]:
    """
    Browse pages, optionally filtered by type.
    Useful when the LLM needs to know what exists before querying.
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            if type_ is not None:
                await cur.execute(
                    """
                    SELECT path, title, type
                    FROM pages
                    WHERE type = %s
                    ORDER BY path
                        LIMIT %s
                    """,
                    (type_, limit),
                )
            else:
                await cur.execute(
                    """
                    SELECT path, title, type
                    FROM pages
                    ORDER BY type, path
                        LIMIT %s
                    """,
                    (limit,),
                )
            return await cur.fetchall()
