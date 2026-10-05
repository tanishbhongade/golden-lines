from dataclasses import dataclass, field

from psycopg_pool import AsyncConnectionPool

from app.core.stores import RelationalStore
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
    links: int = 0
    dangling: list[tuple[str, str, str]] = field(default_factory=list)


async def run_indexer(knowledge_root: str, pool: AsyncConnectionPool) -> IndexStats:
    loader = OKFLoader(knowledge_root)
    splitter = get_splitter()
    ingestion = Ingestion(pool, get_embeddings())
    relational = RelationalStore(pool)

    docs = list(loader.lazy_load())
    stats = IndexStats()

    # Pass 1 — pages + chunks, atomically per file
    for doc in docs:
        page_path = doc.metadata["page_path"]
        new_hash = doc.metadata["hash"]

        existing = await relational.get_page(page_path)
        if existing and existing["hash"] == new_hash:
            stats.skipped += 1
            continue

        chunk_docs = splitter.split_text(doc.page_content)
        carried = {
            "title": doc.metadata["title"],
            "type": doc.metadata["type"],
            "version": doc.metadata["version"],
            "hash": new_hash,
        }
        if "speaker" in doc.metadata:
            carried["speaker"] = doc.metadata["speaker"]
        for c in chunk_docs:
            c.metadata.update(carried)

        n = await ingestion.ingest(
            page_path=page_path,
            page_data={
                "title": doc.metadata["title"],
                "type": doc.metadata["type"],
                "hash": new_hash,
                "version": doc.metadata["version"],
            },
            chunks=chunk_docs,
        )
        stats.added += 1
        stats.chunks += n

    # Pass 2 — relationships
    existing_paths = {p["path"] for p in await relational.list_pages()}
    for doc in docs:
        page_path = doc.metadata["page_path"]
        relations = extract_relationships(doc)
        await relational.delete_relationships_from(page_path)
        for rel_type, target in relations:
            if target not in existing_paths:
                stats.dangling.append((page_path, rel_type, target))
                continue
            await relational.upsert_relationship(page_path, rel_type, target)
            stats.links += 1

    return stats