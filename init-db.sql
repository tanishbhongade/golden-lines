CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Canonical projection: only golden lines
CREATE TABLE golden_lines (
    path        TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    hash        TEXT NOT NULL,
    version     TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Derived: entities referenced from frontmatter
CREATE TABLE entities (
    key          TEXT PRIMARY KEY,
    type         TEXT NOT NULL,
    display_name TEXT NOT NULL,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Derived edges. origin distinguishes frontmatter-declared vs LLM-inferred.
CREATE TABLE relationships (
    source        TEXT NOT NULL REFERENCES golden_lines(path) ON DELETE CASCADE,
    relationship  TEXT NOT NULL,
    target        TEXT NOT NULL REFERENCES entities(key) ON DELETE CASCADE,
    origin        TEXT NOT NULL DEFAULT 'file',
    PRIMARY KEY (source, relationship, target, origin)
);

-- Semantic projection
CREATE TABLE chunks (
    id           BIGSERIAL PRIMARY KEY,
    line_path    TEXT NOT NULL REFERENCES golden_lines(path) ON DELETE CASCADE,
    chunk_index  INT NOT NULL,
    chunk_count  INT NOT NULL,
    content      TEXT NOT NULL,
    embedding    vector(1024),
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Entity resolution cache. LLM-writable, rebuildable.
CREATE TABLE aliases (
    entity_key TEXT NOT NULL REFERENCES entities(key) ON DELETE CASCADE,
    alias      TEXT NOT NULL,
    PRIMARY KEY (entity_key, alias)
);
