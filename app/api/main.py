from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.api.auth import require_token
from app.api.auth import router as auth_router
from app.capture.service import reindex, write_line
from app.core.config import settings
from app.graph import run_query
from app.retrieval import get_page, lines_about, lines_by, list_entities


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = AsyncConnectionPool(
        settings.conninfo,
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


app = FastAPI(title="Golden Lines", lifespan=lifespan)
app.include_router(auth_router)


# ---- query ----

@app.post("/query")
async def query(payload: dict, _=Depends(require_token)):
    question = (payload or {}).get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    result = await run_query(question, app.state.pool)
    return {
        "answer": result["answer"],
        "citations": result["citations"],
    }


# ---- capture ----

@app.post("/capture")
async def capture(payload: dict, _=Depends(require_token)):
    body = (payload or {}).get("body", "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="body is required")

    try:
        path = write_line(
            body=body,
            speaker=payload.get("speaker", "anonymous"),
            topics=payload.get("topics") or [],
            source=payload.get("source"),
            title=payload.get("title"),
        )
    except FileExistsError:
        raise HTTPException(
            status_code=409,
            detail="a line with this title already exists",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    stats = await reindex(app.state.pool)

    return {
        "path": str(path).replace("knowledge/", "").removesuffix(".md"),
        "stats": stats,
    }


# ---- entities ----

@app.get("/entities")
async def entities(
        type: str | None = None,
        limit: int = 100,
        _=Depends(require_token),
):
    return await list_entities(app.state.pool, type_=type, limit=limit)


@app.get("/entities/{key:path}")
async def entity(key: str, _=Depends(require_token)):
    page = await get_page(key, app.state.pool)
    if page is None or "display_name" not in page:
        raise HTTPException(status_code=404, detail="entity not found")
    return page


@app.get("/entities/{key:path}/lines")
async def entity_lines(
        key: str,
        relationship: str = "speaker",
        _=Depends(require_token),
):
    if relationship == "speaker":
        return await lines_by(key, app.state.pool)
    if relationship == "topics":
        return await lines_about(key, app.state.pool)
    raise HTTPException(
        status_code=400,
        detail="relationship must be 'speaker' or 'topics'",
    )


# ---- golden lines ----

@app.get("/lines")
async def lines(limit: int = 200, _=Depends(require_token)):
    async with app.state.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT path, title, updated_at
                FROM golden_lines
                ORDER BY updated_at DESC
                    LIMIT %s
                """,
                (limit,),
            )
            return await cur.fetchall()


@app.get("/lines/{path:path}")
async def line(path: str, _=Depends(require_token)):
    page = await get_page(path, app.state.pool)
    if page is None or page.get("type") != "golden-line":
        raise HTTPException(status_code=404, detail="golden line not found")
    return page


# ---- public ----

@app.get("/health")
async def health():
    """Public — no token required, so you can poll it from anywhere."""
    async with app.state.pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            await cur.fetchone()
    return {"ok": True}
