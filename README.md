# ai-chat

AI support chat over a FAQ / Terms of Service knowledge base. See [plan.md](plan.md) for the roadmap.

Monorepo with two independent projects and no shared tooling:

- `backend/`: Python 3.13, FastAPI, async SQLAlchemy, managed with [uv](https://docs.astral.sh/uv/)
- `frontend/`: Next.js (TypeScript), managed with pnpm

## Getting started

```sh
cp backend/.env.example backend/.env
make db         # Postgres via Docker
make backend    # http://localhost:8000/docs
make frontend   # http://localhost:3000
```

`make lint` runs ruff, mypy and eslint. `make test` runs pytest (needs `make db` first).
