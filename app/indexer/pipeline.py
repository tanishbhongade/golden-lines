from dataclasses import dataclass, field

from psycopg_pool import AsyncConnectionPool

from app.indexer.chunker import get_splitter
from app.indexer.embeddings import get_embeddings
from app.indexer.ingestion import Ingestion
from app.indexer.links import extract_relationships
from app.indexer.loader import OKFLoader


@dataclass
class IndexStats:
    added: int = 0
    skipped: int = 0
    chunks: int = 0
    relationships: int = 0
    new_entities: int = 0
    auto_aliases: int = 0
    dangling: list[tuple[str, str, str]] = field(default_factory=list)


async def _is_unchanged(line_path: str, hash_: str, pool) -> bool:
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT hash FROM golden_lines WHERE path = %s", (line_path,)
            )
            row = await cur.fetchone()
            return row is not None and row["hash"] == hash_


async def run_indexer(knowledge_root: str, pool: AsyncConnectionPool) -> IndexStats:
    loader = OKFLoader(knowledge_root)
    splitter = get_splitter()
    ingestion = Ingestion(pool, get_embeddings())

    docs = list(loader.lazy_load())
    stats = IndexStats()

    for doc in docs:
        line_path = doc.metadata["line_path"]
        hash_ = doc.metadata["hash"]

        if await _is_unchanged(line_path, hash_, pool):
            stats.skipped += 1
            continue

        entity_refs = extract_relationships(doc)

        chunk_docs = splitter.split_text(doc.page_content)
        carried = {
            "title": doc.metadata["title"],
            "version": doc.metadata["version"],
            "hash": hash_,
        }
        if "speaker" in doc.metadata:
            carried["speaker"] = doc.metadata["speaker"]
        for c in chunk_docs:
            c.metadata.update(carried)

        result = await ingestion.ingest(
            line_path=line_path,
            line_data={
                "title": doc.metadata["title"],
                "body": doc.page_content,
                "hash": hash_,
                "version": doc.metadata["version"],
            },
            entity_refs=entity_refs,
            chunks=chunk_docs,
        )

        stats.added += 1
        stats.chunks += result.chunks
        stats.relationships += result.relationships
        stats.new_entities += result.new_entities
        stats.auto_aliases += result.auto_aliases

    return stats
