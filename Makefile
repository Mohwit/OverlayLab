.PHONY: backend-dev frontend-dev test

backend-dev:
	uv run uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd frontend && npm run dev

test:
	uv run pytest
