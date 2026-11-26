.PHONY: up down dev build-front test lint typecheck check-admin-bind loadtest

up:
	docker compose up -d --build

down:
	docker compose down

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

build-front:
	cd frontend && npm ci && npm run build

test:
	pytest -q

lint:
	ruff check shared backend admin tests

typecheck:
	mypy shared backend admin

check-admin-bind:
	@docker compose port admin 8001 | grep -q '^127\.0\.0\.1:' && echo "OK: admin bound to loopback only" || (echo "FAIL: admin port exposed" && exit 1)

loadtest:
	k6 run loadtest/k6_quiz.js
