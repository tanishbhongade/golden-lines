from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool


def _vec(embedding: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


class Ingestion:
    """Atomic write: page row + chunks, one transaction."""

    def __init__(self, pool: AsyncConnectionPool, embeddings: Embeddings):
        self._pool = pool
        self._embeddings = embeddings

    async def ingest(
            self,
            page_path: str,
            page_data: dict,  # title, type, hash, version
            chunks: list[Document],
    ) -> int:
        # embed first — network call, keep the transaction short
        vectors = []
        if chunks:
            vectors = await self._embeddings.aembed_documents(
                [c.page_content for c in chunks]
            )

        async with self._pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    # 1. upsert page (satisfies the FK for step 3)
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
                        (
                            page_path,
                            page_data["title"],
                            page_data["type"],
                            page_data["hash"],
                            page_data["version"],
                        ),
                    )

                    # 2. delete stale chunks
                    await cur.execute(
                        "DELETE FROM chunks WHERE page_path = %s", (page_path,)
                    )

                    # 3. insert fresh chunks
                    for chunk, vec in zip(chunks, vectors):
                        await cur.execute(
                            """
                            INSERT INTO chunks
                                (page_path, content, embedding, metadata)
                            VALUES (%s, %s, %s::vector, %s)
                            """,
                            (
                                page_path,
                                chunk.page_content,
                                _vec(vec),
                                Jsonb(chunk.metadata),
                            ),
                        )

        return len(chunks)
