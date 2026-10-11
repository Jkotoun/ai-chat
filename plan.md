# AI Support Chat

A minimal "AI support" chatbot that answers questions from a knowledge base (FAQ + Terms of Service) stored in Postgres with pgvector. The main goals are to showcase a clean, production-style Python backend (FastAPI, SQLAlchemy, Alembic, tests, Docker) and to have a base to experiment with RAG improvements and tool calling later.

## Goals

- Showcase Python setup and tooling: `uv`, `ruff`, `pytest`, type hints, Docker Compose.
- Showcase FastAPI + async SQLAlchemy 2.0 + Alembic.
- Keep the first version minimal and finishable.
- Serve as a playground for more advanced RAG and tool calling.

## Stack

- **Backend:** Python, FastAPI, SQLAlchemy 2.0 (async), Alembic, pydantic-settings
- **DB:** Postgres + pgvector (via the `pgvector` Python package)
- **Embeddings:** local `fastembed` (e.g. `BAAI/bge-small-en-v1.5`, 384 dims; pick a multilingual model if the data is Czech)
- **LLM:** Groq API (free tier, rate-limited), answers streamed over SSE
- **Frontend:** Next.js (React, TypeScript) chat UI
- **Tooling:** `uv`, `ruff`, `pytest` (async), Docker Compose for Postgres

## Architecture

```
app/
  main.py
  config.py          # pydantic-settings
  db/                # engine, session, models
  api/               # routers, schemas
  services/          # embeddings, retrieval, llm
  ingest.py          # CLI ingestion
alembic/
tests/
docker-compose.yml   # postgres with pgvector
pyproject.toml
frontend/            # Next.js
data/                # FAQ / ToS source files
```

### Data model

`documents` table:

| column      | notes                              |
|-------------|------------------------------------|
| id          | primary key                        |
| source      | `faq` / `tos`                      |
| title       | question (FAQ) or section title    |
| content     | full answer or section text        |
| embedding   | `vector(384)`                      |
| created_at / updated_at | timestamps             |

- FAQ: one row per Q&A pair, embed the question, return question and answer.
- ToS: chunk by section, embed the chunk.

### Ingestion

CLI script (`python -m app.ingest data/`): read markdown/JSON files, chunk, embed, upsert rows. An upload endpoint is out of scope for v1.

### Chat flow

`POST /chat`:
1. Embed the question.
2. Retrieve top-k documents by cosine similarity.
3. Build a prompt with the retrieved snippets.
4. Call Groq and stream the answer back via SSE, together with the sources used.

The system prompt instructs the model to answer only from the provided context and otherwise say it doesn't know and suggest contacting support.

### Design notes

- Keep services behind small interfaces (`Embedder`, `LLMClient`, `retrieve(query) -> list[Document]`) so they are easy to mock in tests and to swap later.
- Frontend: chat box with streaming and a "sources" line under each answer.

## Roadmap

### v1: minimal
- [x] Project setup (`uv`, `ruff`, `pytest`, Docker Compose with pgvector)
- [x] Config, DB session, `documents` model, Alembic migration (extension + table)
- [x] Embedding service (fastembed), run via `asyncio.to_thread` so the blocking model call doesn't block the event loop
- [ ] Ingestion CLI with sample FAQ + ToS data
- [ ] Single-stage retrieval (top 5 by cosine similarity)
- [ ] Groq LLM client, `POST /chat` with SSE streaming and sources
- [ ] Tests (retrieval, API with mocked LLM/embedder)
- [ ] React chat frontend

### v2: better retrieval
- [ ] Retrieve top 20 by vector search, rerank with a cross-encoder (fastembed `TextCrossEncoder`) down to 5
- [ ] Small eval set (20-30 questions with known correct documents), measure hit rate / MRR before and after reranking
- [ ] Multiprocess ingestion (`ProcessPoolExecutor`) with a small benchmark vs single-process and threaded versions, noting where the crossover is (process startup overhead makes it slower for small datasets)
- [ ] Semaphore limiting concurrent Groq calls to stay under the rate limit

### Post-MVP

**Features**
- [ ] Document upload endpoint with background ingestion (see below)
- [ ] Hybrid search (Postgres full-text search + vectors)
- [ ] LLM-generated summaries or hypothetical questions per chunk (small-to-big retrieval) for long ToS text
- [ ] Tool calling (e.g. order status lookup)
- [ ] Conversation history, auth, rate limiting
- [ ] Deployed live demo

**Advanced Python / engineering practice**
- [ ] Worker queue (ARQ or Celery) instead of in-process `BackgroundTasks`
- [ ] `typing.Protocol` for `Embedder` and `LLMClient`
- [ ] Async context managers and dependency injection for DB sessions; lifespan handler that loads models once at startup
- [ ] LRU cache for repeated question embeddings, token-bucket rate limiter per client
- [ ] Structured logging with a request ID propagated via `contextvars`
- [ ] Handle client disconnects / cancellation and timeouts during streaming
- [ ] Multiple Uvicorn/Gunicorn workers for serving (each worker loads its own model copy)

## Concurrency overview

| Where | Tool | Why |
|-------|------|-----|
| API endpoints, DB (`asyncpg`), Groq streaming | `asyncio` | I/O-bound; SSE via async generator; `gather` for independent work; semaphore for rate limit |
| Embeddings, cross-encoder | `asyncio.to_thread` | Sync, CPU-bound onnx inference; releases the GIL, so threads work and the event loop stays free |
| Bulk ingestion | `ProcessPoolExecutor` | CPU-bound parsing/chunking/embedding of many documents; only worth it for large ingests |
| Upload ingestion jobs | `BackgroundTasks`, later a worker queue | Long-running work off the request path |

Priority: `to_thread` for embeddings in v1; multiprocess ingestion benchmark and rate-limit semaphore in v2; worker queue post-MVP.

## Document upload endpoint (post-MVP)

An admin-style endpoint for adding documents to the knowledge base, as an alternative to the CLI ingestion. This is not a user uploading files into the chat.

- `POST /documents` accepts a file (FAQ JSON or ToS markdown), saves it, creates an `ingestion_jobs` row with status `pending`, and returns `202 Accepted` with a job ID.
- A background task chunks, embeds, and inserts the documents, then marks the job `done` or `failed`.
- `GET /jobs/{id}` returns the job status for polling.
- Start with FastAPI `BackgroundTasks` (runs in-process, so a restart loses the job), and note that limitation. A real queue (ARQ/Celery) is the more robust follow-up.
- Out of scope: per-user temporary documents uploaded in the chat (needs per-user data scoping).

## Open questions

- Data language: English or Czech (decides the embedding model).
