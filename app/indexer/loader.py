import hashlib
import json
from pathlib import Path
from typing import Iterator

import frontmatter
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document


def _content_hash(body: str, fm: dict) -> str:
    payload = body + "\n---FM---\n" + json.dumps(fm, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_speaker(speaker):
    if speaker is None:
        return None
    if isinstance(speaker, str) and speaker.startswith("[[") and speaker.endswith("]]"):
        return speaker[2:-2]
    return speaker


class OKFLoader(BaseLoader):
    """OKF/Markdown → Document. Frontmatter → metadata, body → page_content."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def lazy_load(self) -> Iterator[Document]:
        for path in sorted(self.root.rglob("*.md")):
            post = frontmatter.load(path)
            fm = dict(post.metadata)
            body = post.content

            rel = path.relative_to(self.root).with_suffix("")
            slug_path = str(rel).replace("\\", "/")

            metadata = dict(fm)
            metadata.update({
                "page_path": slug_path,
                "title": fm.get("title", path.stem),
                "type": fm.get("type", "unknown"),
                "version": str(fm.get("version", "1.0")),
                "hash": _content_hash(body, fm),
            })
            if "speaker" in metadata:
                metadata["speaker"] = _normalize_speaker(metadata["speaker"])
            metadata = {k: v for k, v in metadata.items() if v is not None}

            yield Document(page_content=body, metadata=metadata)
