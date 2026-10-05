import re
from typing import Iterable

from langchain_core.documents import Document

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

# Frontmatter keys that hold references. Each key becomes a relationship_type.
FM_RELATIONSHIP_KEYS = ("speaker", "topics", "source", "supports", "contradicts")

# Body wikilinks get this relationship_type.
BODY_RELATIONSHIP_TYPE = "mentions"


def _parse_wikilink(raw: str) -> str | None:
    s = raw.strip()
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2]
    if "|" in s:  # [[target|display text]]
        s = s.split("|", 1)[0]
    if "#" in s:  # [[target#anchor]]
        s = s.split("#", 1)[0]
    s = s.strip()
    return s or None


def _targets_from_value(value) -> Iterable[str]:
    """Handles str, list, or nested lists. Accepts both [[slug]] and bare slug."""
    if isinstance(value, str):
        if "[[" in value:
            for m in WIKILINK_RE.finditer(value):
                t = _parse_wikilink(m.group(1))
                if t:
                    yield t
        else:
            s = value.strip()
            if s:
                yield s
    elif isinstance(value, list):
        for item in value:
            yield from _targets_from_value(item)


def extract_relationships(doc: Document) -> list[tuple[str, str]]:
    """Return (relationship_type, target_slug_path) pairs for one Document."""
    relations: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for key in FM_RELATIONSHIP_KEYS:
        value = doc.metadata.get(key)
        if value is None:
            continue
        for target in _targets_from_value(value):
            pair = (key, target)
            if pair not in seen:
                seen.add(pair)
                relations.append(pair)

    for m in WIKILINK_RE.finditer(doc.page_content):
        target = _parse_wikilink(m.group(1))
        if target:
            pair = (BODY_RELATIONSHIP_TYPE, target)
            if pair not in seen:
                seen.add(pair)
                relations.append(pair)

    return relations
