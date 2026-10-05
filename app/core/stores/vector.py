from psycopg_pool import AsyncConnectionPool


class VectorStore:
    """Semantic projection: chunks + embeddings. Metadata is the flexible surface."""

    def __init__(self, pool: AsyncConnectionPool):
        self._pool = pool

    @staticmethod
    def _vec(embedding: list[float]) -> str:
        return "[" + ",".join(repr(float(x)) for x in embedding) + "]"

    async def upsert_chunk(
            self,
            page_path: str,
            content: str,
            embedding: list[float],
            metadata: dict | None = None,
    ) -> int:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO chunks (page_path, content, embedding, metadata)
                    VALUES (%s, %s, %s::vector, %s) RETURNING id
                    """,
                    (page_path, content, self._vec(embedding), metadata or {}),
                )
                return (await cur.fetchone())["id"]

    async def delete_chunks_for_page(self, page_path: str) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM chunks WHERE page_path = %s", (page_path,)
                )

    async def search_similar(
            self,
            embedding: list[float],
            limit: int = 10,
            metadata_filter: dict | None = None,
    ) -> list[dict]:
        """
        metadata_filter is passed straight to JSONB containment (@>).
        Examples:
            {"speaker": "chaitanya"}
            {"version": "1.0", "type": "golden-line"}
        """
        vec = self._vec(embedding)
        clauses = ["embedding IS NOT NULL"]
        params: list = []

        if metadata_filter:
            clauses.append("metadata @> %s::jsonb")
            params.append(metadata_filter)

        where = "WHERE " + " AND ".join(clauses)
        params.extend([vec, vec, limit])

        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    SELECT id, page_path, content, metadata,
                           1 - (embedding <=> %s::vector) AS score
                    FROM chunks
                    {where}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    params,
                )
                return await cur.fetchall()
