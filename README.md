# Golden Lines

A personal knowledge system for capturing, connecting, and retrieving the
sentences worth remembering.

Golden lines are stored as plain Markdown files. Everything else — entities,
relationships, embeddings, search indexes — is a rebuildable projection into
Postgres. If you delete the database, your knowledge is intact.

---

## What it does

- **Capture** a line from the CLI or over HTTP
- **Index** it automatically into a searchable knowledge graph
- **Query** in natural language through an LLM agent that uses tools to
  resolve entities, traverse relationships, and rank by semantic similarity
- **Browse** entities and lines over HTTP

The LLM never writes to your knowledge base. It reads. Only you author.

---

## How it works

```
knowledge/golden-lines/*.md          ← canonical, you write these
│
▼  indexer (deterministic)
golden_lines ─── entities ─── relationships
│
└── chunks (pgvector)
│
▼  retrieval layer
tools ──► LangGraph agent ──► answer
```

Files are the source of truth. Postgres is a projection. Rebuild anytime:

```bash
TRUNCATE chunks, relationships, aliases, entities, golden_lines CASCADE;
python -m app.indexer knowledge/
```

---

## Requirements

- Python 3.12+
- Docker + Docker Compose
- AWS Bedrock access (for embeddings and LLM)

---

## Setup

### 1. Clone and install

```bash
git clone <repo> goldenlines
cd goldenlines
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start Postgres

The compose file lives in a separate services directory, e.g.
`~/local-services/postgres/`. It provides Postgres 18 with pgvector.

```bash
cd ~/local-services/postgres
docker compose up -d
```

Apply the schema on first run:

```bash
docker compose exec -T postgres psql -U tanish -d goldenlines < ./init-db.sql
```

### 3. Configure

Create `.env` in the project root:

```bash
# Postgres
PG_HOST=localhost
PG_PORT=5432
PG_USER=tanish
PG_PASSWORD=<your-password>
PG_DATABASE=goldenlines

# AWS Bedrock
AWS_REGION=ap-south-1
AWS_BEARER_TOKEN_BEDROCK=<your-token>

# Models
EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
EMBEDDING_DIMENSION=1024
LLM_MODEL=deepseek.v3-v1:0

# Auth (JWT)
JWT_SECRET=<generate-with-token-hex-32>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080
AUTH_PASSWORD_HASH=<argon2-hash-of-your-password>
```

Generate the auth secrets:

```bash
# JWT signing key
python -c "import secrets; print(secrets.token_hex(32))"

# Password hash
python -c "from pwdlib import PasswordHash; print(PasswordHash.recommended().hash('YOUR-PASSWORD'))"
```

### 4. Index your corpus

```bash
python -m app.indexer knowledge/
```

---

## Usage

### Capture a golden line

```bash
# minimal
python -m app.capture "You do not rise to the level of your goals; you fall to the level of your systems."

# with speaker and topics
python -m app.capture "Viva la vida - Long live life" \
  -s anonymous \
  -t life

# write only, skip indexing (useful for batches)
python -m app.capture "line one" -n
python -m app.capture "line two" -n
python -m app.indexer knowledge/
```

### Query

```bash
# one-shot
python -m app.query "what did anonymous say about discipline?"

# with tool-call trace
python -m app.query -v "who said viva la vida?"

# interactive
python -m app.query
```

### HTTP API

Start the server:

```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Login and get a token:

```bash
TOKEN=$(curl -s -X POST localhost:8000/auth/login \
  -H 'content-type: application/json' \
  -d '{"password": "YOUR-PASSWORD"}' | jq -r .access_token)
```

Query:

```bash
curl -s -X POST localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"question": "who said viva la vida?"}' | jq
```

Capture:

```bash
curl -s -X POST localhost:8000/capture \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"body": "Viva la vida", "topics": ["life"]}' | jq
```

Browse:

```bash
curl -s localhost:8000/lines          -H "Authorization: Bearer $TOKEN" | jq
curl -s localhost:8000/entities       -H "Authorization: Bearer $TOKEN" | jq
curl -s localhost:8000/health | jq    # public
```

---

## The OKF format

Every golden line is one Markdown file in `knowledge/golden-lines/`.

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

**Rules:**

- The **filename** is the slug. `systems-over-goals.md` → `golden-lines/systems-over-goals`
- The **body** is the line itself. No headers, no links, no formatting
- **Entities are referenced, never authored.** There is no `people/chaitanya-patil.md`. The entity exists because golden lines mention it
- **One line per file**
- **Only you write these files.** No tool, no LLM, no script

### Entity prefixes

| Prefix | Type | Example |
|---|---|---|
| `people/` | person | `people/barney-stinson` |
| `topics/` | topic | `topics/discipline` |
| `sources/` | source | `sources/internet` |

### Anonymous attribution

Use `people/anonymous` like any other entity. It aggregates every
unattributed line:

```markdown
speaker: "[[people/anonymous]]"
```

---

## Project structure

```
goldenlines/
├── knowledge/
│   └── golden-lines/              # canonical, you write here
├── app/
│   ├── core/                      # config, db pool
│   ├── indexer/                   # OKF → Postgres
│   │   ├── loader.py              # parse files
│   │   ├── links.py               # extract frontmatter references
│   │   ├── resolver.py            # entity slug resolution ladder
│   │   ├── chunker/               # body → chunks
│   │   ├── embeddings/            # Bedrock embeddings
│   │   ├── ingestion/             # atomic write to Postgres
│   │   └── pipeline.py            # orchestrates all of the above
│   ├── retrieval/                 # pure data access
│   │   ├── resolve.py             # name → entity
│   │   ├── pages.py               # get_page, list_entities
│   │   ├── relationships.py       # lines_by, lines_about, get_related
│   │   └── search.py              # semantic + hybrid search
│   ├── tools/                     # LLM-callable wrappers
│   ├── graph/                     # LangGraph orchestration
│   │   ├── state.py
│   │   ├── nodes/agent.py
│   │   └── query_graph.py
│   ├── capture/                   # write golden lines
│   │   ├── service.py             # shared by CLI and API
│   │   └── __main__.py            # CLI entry
│   ├── query/
│   │   └── __main__.py            # CLI entry
│   └── api/
│       ├── auth.py                # JWT
│       └── main.py                # FastAPI routes
├── scripts/                       # dev/test scripts
├── docker-compose.yml             # may live in a services dir
├── init-db.sql
├── requirements.txt
└── .env
```

Each layer imports only from layers above it. `retrieval/` never imports
from `tools/` or `graph/`. `tools/` never imports from `graph/`.

---

## Design principles

1. **OKF/Markdown is canonical.** Human-readable, portable, git-friendly
2. **Postgres is a projection.** Delete it, re-index, identical state
3. **Only the author writes knowledge.** The LLM reads and reasons, never writes
4. **Grounding is deterministic.** Entity resolution uses exact match,
   aliases, and trigram similarity — not LLM guessing
5. **The LLM selects tools; tools return facts.** The model routes, the
   code computes

---

## Database schema

| Table | Purpose | Written by |
|---|---|---|
| `golden_lines` | Projection of OKF files | Indexer |
| `entities` | Distinct slugs from frontmatter | Indexer |
| `relationships` | Edges (`origin='file'` or `'llm'`) | Indexer, LLM |
| `chunks` | Embeddable text + vectors | Indexer |
| `aliases` | Entity resolution cache | Indexer, LLM |

Five tables. Two extensions (`vector`, `pg_trgm`).

---

## Entity resolution

When the indexer encounters a slug it doesn't recognize, it tries:

1. **Exact key** — `entities.key = slug`
2. **Exact alias** — `aliases.alias = slug`
3. **Trigram ≥ 0.85** — `similarity(key, slug)` → auto-alias
4. **New entity** — insert and return

This means a typo like `people/chaitnya-patil` silently resolves to
`people/chaitanya-patil`. The file stays as written. The derived layer
is corrected.

---

## Models

All model choices are environment variables. Swapping either is a config
change, not a code change.

| Component | Default | Why |
|---|---|---|
| Embeddings | `amazon.titan-embed-text-v2:0` | In-region, cheap, 1024d |
| LLM | `deepseek.v3-v1:0` | In-region, reliable tool calling |

**Note on Bedrock model IDs.** Nova models require an inference profile
prefix (`apac.`, `us.`). DeepSeek V3.1 does not — use the bare ID
`deepseek.v3-v1:0`.

---

## Operational notes

### Re-index

```bash
python -m app.indexer knowledge/
```

Idempotent. Files whose content hash is unchanged are skipped.

### Reset the database

```sql
TRUNCATE chunks, relationships, aliases, entities, golden_lines CASCADE;
```

Then re-index. Your files are untouched.

### Inspect

```bash
docker compose exec postgres psql -U tanish -d goldenlines

SELECT path, title FROM golden_lines;
SELECT key, type, display_name FROM entities ORDER BY type, key;
SELECT source, relationship, target FROM relationships;
SELECT line_path, chunk_index, chunk_count FROM chunks;
SELECT * FROM aliases;
```

---

## Adding from mobile (later)

The HTTP API is reachable on your LAN. When you want to capture from a
phone:

- **Tailscale** — install on laptop and phone, use the Tailscale IP
  instead of the LAN IP. No port forwarding, encrypted, works anywhere
- **HTTP Request Shortcuts** (Android) — home-screen widget firing
  `POST /capture` with a bearer token
- **Tasker** (Android) — native HTTP action, share-sheet integration
- **Telegram bot** — a small Python script that turns messages into
  golden lines

The API needs no changes for any of these.

---

## What's not built

Deliberately out of scope for now:

- Multi-user support
- Web UI
- Golden-line-to-golden-line relationships (`supports`, `contradicts`)
- Spaced repetition
- Graph visualization
- MCP server

Build them when the corpus and usage tell you they're needed. Not before.

---

## License

MIT
