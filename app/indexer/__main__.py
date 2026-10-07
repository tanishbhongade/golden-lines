import argparse
import asyncio
import sys

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings
from app.indexer.pipeline import run_indexer


async def _run(root: str, verbose: bool) -> int:
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
        stats = await run_indexer(root, pool)
    finally:
        await pool.close()

    print(f"added:         {stats.added}")
    print(f"skipped:       {stats.skipped}")
    print(f"chunks:        {stats.chunks}")
    print(f"relationships: {stats.relationships}")
    print(f"new_entities:  {stats.new_entities}")
    print(f"auto_aliases:  {stats.auto_aliases}")

    if stats.dangling:
        print(f"dangling:      {len(stats.dangling)}")
        if verbose:
            for src, rel, target in stats.dangling:
                print(f"  {src} --[{rel}]--> {target}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.indexer")
    parser.add_argument("knowledge_root", help="path to knowledge/ directory")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="print each dangling reference",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.knowledge_root, args.verbose))


if __name__ == "__main__":
    sys.exit(main())