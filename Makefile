.PHONY: db up down migrate backend frontend lint test

db:
	docker compose up -d db

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	cd backend && uv run alembic upgrade head

backend:
	cd backend && uv run uvicorn app.main:app --reload

frontend:
	cd frontend && pnpm dev

lint:
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy .
	cd frontend && pnpm lint

test:
	cd backend && uv run pytest
