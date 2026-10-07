from functools import lru_cache

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.indexer.embeddings import get_embeddings
from app.retrieval.relationships import lines_about, lines_by


def _vec(embedding: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


@lru_cache(maxsize=1)
def _embedder():
    return get_embeddings()


async def _embed_query(query: str) -> str:
    vectors = await _embedder().aembed_documents([query])
    return _vec(vectors[0])


async def semantic_search(
        query: str,
        pool: AsyncConnectionPool,
        limit: int = 5,
        metadata_filter: dict | None = None,
) -> list[dict]:
    vec = await _embed_query(query)

    clauses = ["embedding IS NOT NULL"]
    where_params: list = []
    if metadata_filter:
        clauses.append("metadata @> %s::jsonb")
        where_params.append(Jsonb(metadata_filter))
    where = "WHERE " + " AND ".join(clauses)

    params = [vec, *where_params, vec, limit]

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT line_path, chunk_index, chunk_count, content, metadata,
                       1 - (embedding <=> %s::vector) AS score
                FROM chunks
                {where}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                params,
            )
            return await cur.fetchall()


async def hybrid_search(
        query: str,
        pool: AsyncConnectionPool,
        speaker: str | None = None,
        topic: str | None = None,
        limit: int = 5,
) -> list[dict]:
    allowed: set[str] | None = None
    if speaker is not None:
        rows = await lines_by(speaker, pool)
        allowed = {r["path"] for r in rows}
    if topic is not None:
        rows = await lines_about(topic, pool)
        topic_paths = {r["path"] for r in rows}
        allowed = topic_paths if allowed is None else allowed & topic_paths

    if allowed is not None and not allowed:
        return []

    vec = await _embed_query(query)

    clauses = ["embedding IS NOT NULL"]
    where_params: list = []
    if allowed is not None:
        clauses.append("line_path = ANY(%s::text[])")
        where_params.append(list(allowed))
    where = "WHERE " + " AND ".join(clauses)

    params = [vec, *where_params, vec, limit]

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT line_path, chunk_index, chunk_count, content, metadata,
                       1 - (embedding <=> %s::vector) AS score
                FROM chunks
                {where}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                params,
            )
            return await cur.fetchall()
