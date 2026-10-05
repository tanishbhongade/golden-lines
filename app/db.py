import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row


def _conninfo() -> str:
    return " ".join([
        f"host={os.getenv('PGHOST', 'localhost')}",
        f"port={os.getenv('PGPORT', '5432')}",
        f"user={os.getenv('PGUSER', 'postgres')}",
        f"password={os.getenv('PGPASSWORD', 'postgres')}",
        f"dbname={os.getenv('PGDATABASE', 'postgres')}",
    ])


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = AsyncConnectionPool(
        _conninfo(),
        open=False,
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row},
    )
    await pool.open()
    await pool.wait()
    app.state.pool = pool
    try:
        yield
    finally:
        await pool.close()


async def get_pool(request: Request) -> AsyncConnectionPool:
    """FastAPI dependency: returns the app-wide async pool."""
    return request.app.state.pool


async def verify_pgvector(pool: AsyncConnectionPool) -> dict:
    """Confirm pgvector + pg_trgm are live and the vector type round-trips."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                              SELECT extname, extversion
                              FROM pg_extension
                              WHERE extname IN ('vector', 'pg_trgm')
                              ORDER BY extname
                              """)
            exts = {r["extname"]: r["extversion"] for r in await cur.fetchall()}

            await cur.execute(
                "SELECT '[1,2,3]'::vector <-> '[4,5,6]'::vector AS dist"
            )
            dist = (await cur.fetchone())["dist"]

            await cur.execute("SELECT similarity('chaitnya', 'chaitanya') AS sim")
            sim = (await cur.fetchone())["sim"]

    return {
        "extensions": exts,
        "vector_ok": "vector" in exts,
        "pg_trgm_ok": "pg_trgm" in exts,
        "sample_l2_distance": dist,
        "sample_trgm_similarity": sim,
    }