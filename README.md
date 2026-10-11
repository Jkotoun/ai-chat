# ai-chat

AI support chat over a FAQ / Terms of Service knowledge base.

Monorepo with two independent projects and no shared tooling:

- `backend/`: Python 3.14, FastAPI, async SQLAlchemy, managed with [uv](https://docs.astral.sh/uv/)
- `frontend/`: Next.js (TypeScript), managed with pnpm

## Getting started

```sh
cp backend/.env.example backend/.env
docker compose up -d db                                      # Postgres + pgvector
(cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload)
# in a second terminal:
cd frontend && pnpm install && pnpm dev                      # http://localhost:3000
```

Backend checks (run in `backend/`; tests need the DB running):

```sh
uv run ruff format --check . && uv run ruff check . && uv run mypy .
uv run pytest
```

Migrations (run in `backend/`; the DB must be at head first):

```sh
uv run alembic upgrade head                                  # apply pending migrations
uv run alembic check                                         # fails if models changed without a migration
uv run alembic revision --autogenerate -m "add users"        # generate one, then review it
```

Frontend: `pnpm lint` in `frontend/`.
