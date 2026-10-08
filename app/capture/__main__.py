import argparse
import asyncio
import sys
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.capture.service import reindex, write_line
from app.core.config import settings


async def _run_reindex() -> None:
    pool = AsyncConnectionPool(
        settings.conninfo,
        open=False,
        min_size=1,
        max_size=5,
        kwargs={"row_factory": dict_row},
    )
    await pool.open()
    await pool.wait()
    try:
        stats = await reindex(pool)
    finally:
        await pool.close()
    print(f"indexed: {stats}")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="app.capture",
        description="Add a golden line to the knowledge base.",
    )
    parser.add_argument("body", help="the golden line text")
    parser.add_argument("--title", help="title (default: first few words)")
    parser.add_argument(
        "-s", "--speaker",
        default="anonymous",
        help="speaker slug (default: anonymous)",
    )
    parser.add_argument(
        "-t", "--topic",
        action="append",
        default=[],
        help="topic slug (repeatable)",
    )
    parser.add_argument("-S", "--source", default=None, help="source slug")
    parser.add_argument(
        "-n", "--no-index",
        action="store_true",
        help="skip running the indexer after writing",
    )
    args = parser.parse_args()

    if not Path("knowledge").exists():
        print(
            "error: run from the project root (no 'knowledge/' directory)",
            file=sys.stderr,
        )
        return 1

    try:
        path = write_line(
            body=args.body,
            speaker=args.speaker,
            topics=args.topic,
            source=args.source,
            title=args.title,
        )
    except (FileExistsError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"wrote {path}")

    if not args.no_index:
        asyncio.run(_run_reindex())

    return 0


if __name__ == "__main__":
    sys.exit(main())
