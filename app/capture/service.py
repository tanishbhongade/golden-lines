import re
from pathlib import Path

from psycopg_pool import AsyncConnectionPool

from app.indexer.pipeline import run_indexer

KNOWLEDGE_DIR = Path("knowledge/golden-lines")


def _slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def _normalize_slug(value: str, prefix: str) -> str:
    if value.startswith(f"{prefix}/"):
        return value[len(prefix) + 1:]
    return value


def _title_from_body(body: str, max_words: int = 8) -> str:
    return " ".join(body.split()[:max_words])


def _yaml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _render(data: dict) -> str:
    lines = ["---", "type: golden-line"]
    lines.append(f"title: {_yaml_str(data['title'])}")
    lines.append('version: "1.0"')

    speaker = data["speaker"]
    lines.append(f"speaker: {_yaml_str(f'[[people/{speaker}]]')}")

    if data["topics"]:
        lines.append("topics:")
        for t in data["topics"]:
            lines.append(f"  - {_yaml_str(f'[[topics/{t}]]')}")

    if data["source"]:
        source = data["source"]
        lines.append(f"source: {_yaml_str(f'[[sources/{source}]]')}")

    lines.append("---")
    lines.append("")
    lines.append(data["body"].strip())
    lines.append("")
    return "\n".join(lines)


def write_line(
        body: str,
        speaker: str = "anonymous",
        topics: list[str] | None = None,
        source: str | None = None,
        title: str | None = None,
) -> Path:
    """
    Write a golden line file. Returns the path.
    Raises FileExistsError on filename collision, ValueError on bad input.
    """
    body = body.strip()
    if not body:
        raise ValueError("empty body")

    title = (title or _title_from_body(body)).strip()
    slug = _slugify(title)
    if not slug:
        raise ValueError("title slugifies to empty string")

    path = KNOWLEDGE_DIR / f"{slug}.md"
    if path.exists():
        raise FileExistsError(str(path))

    data = {
        "title": title,
        "body": body,
        "speaker": _normalize_slug(speaker, "people"),
        "topics": [_normalize_slug(t, "topics") for t in (topics or [])],
        "source": _normalize_slug(source, "sources") if source else None,
    }
    path.write_text(_render(data), encoding="utf-8")
    return path


async def reindex(pool: AsyncConnectionPool) -> dict:
    """Run the indexer and return the stats as a plain dict."""
    stats = await run_indexer("knowledge/", pool)
    return {
        "added": stats.added,
        "skipped": stats.skipped,
        "chunks": stats.chunks,
        "relationships": stats.relationships,
        "new_entities": stats.new_entities,
        "auto_aliases": stats.auto_aliases,
    }
