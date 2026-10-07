from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.indexer.resolver import resolve_slug


def _vec(embedding: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


@dataclass
class IngestResult:
    chunks: int
    relationships: int
    new_entities: int
    auto_aliases: int


class Ingestion:
    def __init__(self, pool: AsyncConnectionPool, embeddings: Embeddings):
        self._pool = pool
        self._embeddings = embeddings

    async def ingest(
            self,
            line_path: str,
            line_data: dict,
            entity_refs: list[tuple[str, str]],
            chunks: list[Document],
    ) -> IngestResult:
        # Embed outside the transaction — network call, keep the tx short.
        vectors = []
        if chunks:
            vectors = await self._embeddings.aembed_documents(
                [c.page_content for c in chunks]
            )

        new_entities = 0
        auto_aliases = 0
        relationships = 0

        async with self._pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    # 1. upsert golden line
                    await cur.execute(
                        """
                        INSERT INTO golden_lines (path, title, body, hash, version, updated_at)
                        VALUES (%s, %s, %s, %s, %s, NOW()) ON CONFLICT (path) DO
                        UPDATE SET
                            title = EXCLUDED.title,
                            body = EXCLUDED.body,
                            hash = EXCLUDED.hash,
                            version = EXCLUDED.version,
                            updated_at = NOW()
                        """,
                        (
                            line_path,
                            line_data["title"],
                            line_data["body"],
                            line_data["hash"],
                            line_data["version"],
                        ),
                    )

                    # 2. resolve entity refs and write relationships (origin='file')
                    await cur.execute(
                        "DELETE FROM relationships WHERE source = %s AND origin = 'file'",
                        (line_path,),
                    )
                    for rel_type, slug in entity_refs:
                        canonical, resolution = await resolve_slug(cur, slug)
                        if resolution == "new":
                            new_entities += 1
                        elif resolution == "auto-alias":
                            auto_aliases += 1
                        await cur.execute(
                            """
                            INSERT INTO relationships (source, relationship, target, origin)
                            VALUES (%s, %s, %s, 'file') ON CONFLICT DO NOTHING
                            """,
                            (line_path, rel_type, canonical),
                        )
                        relationships += 1

                    # 3. replace chunks
                    await cur.execute(
                        "DELETE FROM chunks WHERE line_path = %s", (line_path,)
                    )
                    chunk_count = len(chunks)
                    for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
                        await cur.execute(
                            """
                            INSERT INTO chunks
                                (line_path, chunk_index, chunk_count, content, embedding, metadata)
                            VALUES (%s, %s, %s, %s, %s::vector, %s)
                            """,
                            (
                                line_path,
                                idx,
                                chunk_count,
                                chunk.page_content,
                                _vec(vec),
                                Jsonb(chunk.metadata),
                            ),
                        )

        return IngestResult(
            chunks=len(chunks),
            relationships=relationships,
            new_entities=new_entities,
            auto_aliases=auto_aliases,
        )
