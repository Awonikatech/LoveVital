.PHONY: up down logs migrate seed test test-backend test-frontend e2e dev-api dev-web
up:            ; docker compose up --build -d
down:          ; docker compose down
logs:          ; docker compose logs -f backend
migrate:       ; cd backend && alembic upgrade head
seed:          ; cd backend && python -m scripts.seed
dev-api:       ; cd backend && uvicorn app.main:app --reload --port 8000
dev-web:       ; cd frontend && npm run dev
test-backend:  ; cd backend && ENVIRONMENT=test python -m pytest -q
test-frontend: ; cd frontend && npm test
test: test-backend test-frontend
e2e:           ; cd frontend && npm run e2e
