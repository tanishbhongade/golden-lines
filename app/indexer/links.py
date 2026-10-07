import re
from typing import Iterable

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

# Frontmatter keys that hold references. Only entity targets supported for now.
FM_RELATIONSHIP_KEYS = ("speaker", "topics", "source")


def _parse_wikilink(raw: str) -> str | None:
    s = raw.strip()
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2]
    if "|" in s:
        s = s.split("|", 1)[0]
    if "#" in s:
        s = s.split("#", 1)[0]
    s = s.strip()
    return s or None


def _targets_from_value(value) -> Iterable[str]:
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


def extract_relationships(doc) -> list[tuple[str, str]]:
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
    return relations
