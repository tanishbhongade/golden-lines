import argparse
import asyncio
import sys

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings
from app.graph import run_query


def _preview(content, n: int = 120) -> str:
    if isinstance(content, list):
        content = "".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    if not content:
        return ""
    text = " ".join(str(content).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _print_trace(messages: list) -> None:
    print("\n--- trace ---")
    for i, m in enumerate(messages):
        kind = type(m).__name__
        tool_calls = getattr(m, "tool_calls", None)
        if tool_calls:
            print(f"  [{i}] {kind}:")
            for tc in tool_calls:
                print(f"        → {tc.get('name')}({tc.get('args', {})})")
        elif kind == "ToolMessage":
            name = getattr(m, "name", "?")
            print(f"  [{i}] {kind} ({name}): {_preview(m.content)}")
        else:
            print(f"  [{i}] {kind}: {_preview(m.content)}")


def _make_pool() -> AsyncConnectionPool:
    return AsyncConnectionPool(
        settings.conninfo,
        open=False,
        min_size=1,
        max_size=5,
        kwargs={"row_factory": dict_row},
    )


async def _ask_once(question: str, verbose: bool) -> int:
    pool = _make_pool()
    await pool.open()
    await pool.wait()
    try:
        result = await run_query(question, pool)
    finally:
        await pool.close()

    print(result["answer"])
    if verbose:
        if result.get("citations"):
            print("\n--- citations ---")
            for c in result["citations"]:
                print(f"  {c}")
        _print_trace(result["messages"])
    return 0


async def _interactive(verbose: bool) -> int:
    pool = _make_pool()
    await pool.open()
    await pool.wait()
    print("Golden Lines query. Blank line or Ctrl-D to exit.\n")
    try:
        while True:
            try:
                question = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not question:
                break
            result = await run_query(question, pool)
            print()
            print(result["answer"])
            if verbose:
                if result.get("citations"):
                    print("\n--- citations ---")
                    for c in result["citations"]:
                        print(f"  {c}")
                _print_trace(result["messages"])
            print()
    finally:
        await pool.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.query")
    parser.add_argument(
        "question",
        nargs="*",
        help="question to ask (omit for interactive mode)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="print the tool-call trace",
    )
    args = parser.parse_args()

    if args.question:
        return asyncio.run(_ask_once(" ".join(args.question), args.verbose))
    return asyncio.run(_interactive(args.verbose))


if __name__ == "__main__":
    sys.exit(main())