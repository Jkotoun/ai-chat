.PHONY: db down backend frontend lint test

db:
	docker compose up -d db

down:
	docker compose down

backend:
	cd backend && uv run uvicorn app.main:app --reload

frontend:
	cd frontend && pnpm dev

lint:
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy .
	cd frontend && pnpm lint

test:
	cd backend && uv run pytest
