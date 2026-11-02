# Golden Lines

Golden Lines is a personal knowledge system for capturing, connecting, and retrieving the sentences worth remembering.

Knowledge is authored as plain Markdown files. PostgreSQL stores a rebuildable projection containing entities, relationships, search chunks, and embeddings. If the database is deleted, the source files remain intact.

## Features

- Capture golden lines from the CLI or HTTP API
- Index Markdown files into PostgreSQL with `pgvector`
- Resolve people, topics, and sources into a lightweight knowledge graph
- Search and query the collection with an LLM agent
- Browse lines and entities over HTTP
- Keep the LLM read-only: only the author writes knowledge files

## Architecture

```text
knowledge/**/*.md
        │
        ▼
  deterministic indexer
        │
        ├── golden_lines
        ├── entities
        ├── relationships
        └── chunks + embeddings
        │
        ▼
 retrieval tools → LangGraph agent → answer
```

The Markdown corpus is the source of truth. PostgreSQL can be rebuilt at any time:

```bash
TRUNCATE chunks, relationships, entities, golden_lines CASCADE;
python -m app.indexer knowledge/
```

## Requirements

- Python 3.12+
- Docker and Docker Compose
- PostgreSQL with the `vector` and `pg_trgm` extensions
- AWS Bedrock access for embeddings and the LLM

## Setup

### 1. Clone and install

```bash
git clone https://github.com/tanishbhongade/golden-lines.git
cd golden-lines

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure PostgreSQL

Copy the example environment file and fill in the required values:

```bash
cp .env.example .env
```

The repository includes a Compose example for a `pgvector` database:

```bash
docker compose -f docker-compose.example.yml up -d
```

The schema is mounted into the container and is applied automatically when the database volume is initialized. To apply it manually:

```bash
psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DATABASE" -f init-db.sql
```

### 3. Configure AWS Bedrock and authentication

Set these values in `.env`:

```dotenv
PG_HOST=localhost
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=change-me
PG_DATABASE=goldenlines

AWS_REGION=ap-south-1
AWS_BEARER_TOKEN_BEDROCK=
EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
EMBEDDING_DIMENSION=1024
LLM_MODEL=deepseek.v3-v1:0

JWT_SECRET=
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080
AUTH_PASSWORD_HASH=
```

Generate a signing key and password hash:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
python -c "from pwdlib import PasswordHash; print(PasswordHash.recommended().hash('YOUR-PASSWORD'))"
```

### 4. Index the corpus

The indexer accepts a path to a directory containing Markdown files:

```bash
python -m app.indexer knowledge/
```

Indexing is idempotent. Unchanged files are skipped.

## Knowledge file format

Each golden line is one Markdown file under `knowledge/`. The filename becomes the line slug, frontmatter stores metadata, and the body contains the line itself.

```markdown
---
type: golden-line
title: Systems over goals
version: "1.0"
speaker: "[[people/chaitanya-patil]]"
topics:
  - "[[topics/discipline]]"
source: "[[sources/podcast-123]]"
---

You do not rise to the level of your goals; you fall to the level of your systems.
```

### File rules

- Use one golden line per Markdown file.
- Keep the body to the line itself; do not add headings or formatting.
- The filename is the slug: `systems-over-goals.md` becomes `systems-over-goals`.
- Entity files are not required. Entities are created from frontmatter references.
- Use `people/anonymous` for unattributed lines.

Supported relationship fields are `speaker`, `topics`, and `source`. Common entity prefixes are:

| Prefix | Type | Example |
| --- | --- | --- |
| `people/` | Person | `people/barney-stinson` |
| `topics/` | Topic | `topics/discipline` |
| `sources/` | Source | `sources/internet` |

## CLI usage

### Capture a line

```bash
python -m app.capture \
  "You do not rise to the level of your goals; you fall to the level of your systems." \
  --speaker people/james-clear \
  --topic discipline \
  --source sources/atomic-habits
```

Options include `--title`, repeatable `--topic`, `--source`, and `--no-index`. Use `--no-index` to write several files and index them as a batch:

```bash
python -m app.capture "First line" --no-index
python -m app.capture "Second line" --no-index
python -m app.indexer knowledge/
```

### Query the collection

```bash
# One-shot query
python -m app.query "What did James Clear say about discipline?"

# Interactive mode
python -m app.query

# Include citations and the tool-call trace
python -m app.query --verbose "Who said this line?"
```

## HTTP API

Start the API:

```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Authenticate:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'content-type: application/json' \
  -d '{"password":"YOUR-PASSWORD"}' | jq -r .access_token)
```

Query and capture:

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"question":"What did James Clear say about discipline?"}' | jq

curl -s -X POST http://localhost:8000/capture \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"body":"Viva la vida","topics":["life"]}' | jq
```

Browse the collection:

```bash
curl -s http://localhost:8000/lines \
  -H "Authorization: Bearer $TOKEN" | jq

curl -s http://localhost:8000/entities \
  -H "Authorization: Bearer $TOKEN" | jq

curl -s http://localhost:8000/health | jq
```

`/health` is public. All other application endpoints require a bearer token.

## Project structure

```text
golden-lines/
├── knowledge/
│   └── golden-lines/              # Canonical Markdown corpus
│       └── *.md                   # One authored golden line per file
├── app/
│   ├── api/
│   │   ├── auth.py                # Login, password verification, JWT bearer auth
│   │   └── main.py                # FastAPI app and HTTP endpoints
│   ├── capture/
│   │   ├── __main__.py            # `python -m app.capture`
│   │   └── service.py             # Validate and write Markdown lines; trigger re-indexing
│   ├── core/
│   │   ├── config.py              # Environment-backed application settings
│   │   └── stores/
│   │       ├── relational.py      # PostgreSQL relational queries
│   │       └── vector.py          # Vector/semantic search queries
│   ├── graph/
│   │   ├── nodes/
│   │   │   └── agent.py           # LLM agent node and tool execution
│   │   ├── query_graph.py         # Build and run the LangGraph query flow
│   │   └── state.py               # Shared graph state and query result types
│   ├── indexer/
│   │   ├── __main__.py            # `python -m app.indexer`
│   │   ├── chunker/
│   │   │   └── default.py         # Split line text into embedding chunks
│   │   ├── embeddings/
│   │   │   └── default.py         # AWS Bedrock embedding provider
│   │   ├── ingestion/
│   │   │   └── default.py         # Atomic PostgreSQL projection writes
│   │   ├── links.py               # Extract frontmatter relationships
│   │   ├── loader.py               # Load and normalize Markdown/frontmatter
│   │   ├── pipeline.py             # Coordinate loading, chunking, embedding, ingestion
│   │   └── resolver.py             # Resolve and create referenced entities
│   ├── query/
│   │   └── __main__.py            # `python -m app.query` one-shot and interactive CLI
│   ├── retrieval/
│   │   ├── pages.py                # Fetch lines and entity pages
│   │   ├── relationships.py        # Find lines by speaker/topic and related entities
│   │   ├── resolve.py              # Resolve human names and entity keys
│   │   └── search.py               # Semantic and hybrid search
│   └── tools/
│       ├── pages.py                # Agent tool wrappers for page retrieval
│       ├── relationships.py        # Agent tool wrappers for graph traversal
│       ├── resolve.py              # Agent tool wrapper for entity resolution
│       └── search.py               # Agent tool wrapper for search
├── docker-compose.example.yml      # Local pgvector/PostgreSQL service
├── init-db.sql                     # Database extensions, tables, and indexes
├── requirements.txt                # Python runtime dependencies
├── .env.example                    # Configuration template
├── .gitignore
├── LICENSE
└── README.md
```

### Runtime flow

```text
Capture CLI / POST /capture
              │
              ▼
   app.capture.service.write_line
              │
              ▼
   knowledge/golden-lines/*.md
              │
              ▼
      app.indexer.pipeline
       ├── loader + links
       ├── chunker + embeddings
       ├── resolver
       └── ingestion → PostgreSQL

Query CLI / POST /query
              │
              ▼
      app.graph.query_graph
              │
              ▼
          agent node
              │
              ├── retrieval tools
              │    ├── resolve
              │    ├── search
              │    ├── pages
              │    └── relationships
              │
              ▼
       grounded answer + citations
```

### Data ownership

| Area | Responsibility | Source of truth |
| --- | --- | --- |
| `knowledge/golden-lines/` | Authored line text and metadata | Markdown files |
| `app/indexer/` | Derived database projection | Markdown input |
| `app/retrieval/` | Deterministic reads from the projection | PostgreSQL |
| `app/tools/` | LLM-facing retrieval interface | Retrieval functions |
| `app/graph/` | Query planning and answer generation | Tool results + LLM |
| `app/api/` and CLI modules | User-facing entry points | Services and graph |

## Design principles

1. **Markdown is canonical.** The corpus is human-readable, portable, and Git-friendly.
2. **PostgreSQL is a projection.** Re-indexing reconstructs the derived state.
3. **The author writes knowledge.** The LLM can retrieve and reason, but does not author files.
4. **Grounding is deterministic.** Entity resolution and retrieval are implemented in code.
5. **Tools return facts.** The LLM selects retrieval tools; the tools perform the data access.

## License

MIT
