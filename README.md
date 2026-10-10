# ai-chat

AI support chat over a FAQ / Terms of Service knowledge base. Retrieval-augmented generation with Postgres + pgvector and Groq. See [plan.md](plan.md) for the roadmap.

Monorepo with two independent projects and no shared tooling:

- `backend/`: Python 3.13, FastAPI, async SQLAlchemy, Alembic, managed with [uv](https://docs.astral.sh/uv/)
- `frontend/`: Next.js (TypeScript), managed with pnpm

## Getting started

```sh
cp backend/.env.example backend/.env   # then set GROQ_API_KEY
make db                                # Postgres + pgvector via Docker
make migrate
make backend                           # http://localhost:8000/docs
make frontend                          # http://localhost:3000
```

`make lint` and `make test` run checks (ruff, mypy, pytest, eslint).
