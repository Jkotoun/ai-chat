# ai-chat

AI support chat over a FAQ / Terms of Service knowledge base. See [plan.md](plan.md) for the roadmap.

Monorepo with two independent projects and no shared tooling:

- `backend/`: Python 3.14, FastAPI, async SQLAlchemy, managed with [uv](https://docs.astral.sh/uv/)
- `frontend/`: Next.js (TypeScript), managed with pnpm

## Getting started

```sh
cp backend/.env.example backend/.env
docker compose up -d db                                      # Postgres
(cd backend && uv sync && uv run uvicorn app.main:app --reload)  # http://localhost:8000/docs
# in a second terminal:
cd frontend && pnpm install && pnpm dev                      # http://localhost:3000
```

Backend checks (run in `backend/`; tests need the DB running):

```sh
uv run ruff format --check . && uv run ruff check . && uv run mypy .
uv run pytest
```

Frontend: `pnpm lint` in `frontend/`.
