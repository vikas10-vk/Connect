# =============================================================================
# Makefile — Developer shortcuts for ProConnect (ProConnect clone)
# =============================================================================
#
# Usage:
#   make <target>
#
# Examples:
#   make dev         - Boot environment in Docker Compose
#   make test        - Run backend test suite
#   make lint        - Run all linters (ruff, mypy, eslint)
#   make migrate     - Run database migrations (Alembic)
#   make seed        - Seed database with categories & initial data
# =============================================================================

.PHONY: help dev build down logs ps test lint format migrate seed clean-docker shell-backend shell-frontend

# Default target: show help
help:
	@echo "============================================================================="
	@echo "ProConnect Developer CLI"
	@echo "============================================================================="
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  dev              Start development servers (Docker Compose)"
	@echo "  build            Build or rebuild services"
	@echo "  down             Stop services and remove containers"
	@echo "  logs             Tail all docker-compose logs"
	@echo "  ps               List active service containers"
	@echo "  test             Run pytest test suite in backend container"
	@echo "  lint             Run linters (Ruff/Mypy backend, ESLint frontend)"
	@echo "  format           Automatically format backend code (Ruff)"
	@echo "  migrate          Apply database migrations to current state"
	@echo "  seed             Seed database with standard categories and sample data"
	@echo "  clean-docker     Delete all volumes, dangling images, and system caches"
	@echo "  shell-backend    Open interactive sh inside the backend container"
	@echo "  shell-frontend   Open interactive sh inside the frontend container"
	@echo "============================================================================="

# Docker Compose actions
dev:
	docker compose -f docker-compose.dev.yml up

build:
	docker compose -f docker-compose.dev.yml build

down:
	docker compose -f docker-compose.dev.yml down

logs:
	docker compose -f docker-compose.dev.yml logs -f

ps:
	docker compose -f docker-compose.dev.yml ps

# Backend & testing shortcuts
test:
	docker compose -f docker-compose.dev.yml exec fastapi pytest

lint:
	@echo "--- Linting backend with Ruff ---"
	docker compose -f docker-compose.dev.yml exec fastapi ruff check .
	@echo "--- Type-checking backend with Mypy ---"
	docker compose -f docker-compose.dev.yml exec fastapi mypy .
	@echo "--- Linting frontend with ESLint ---"
	docker compose -f docker-compose.dev.yml exec nextjs npm run lint

format:
	docker compose -f docker-compose.dev.yml exec fastapi ruff format .

# Database & Migrations
migrate:
	docker compose -f docker-compose.dev.yml exec fastapi alembic upgrade head

seed:
	docker compose -f docker-compose.dev.yml exec fastapi python -m seeds.seed_categories

# System tools
clean-docker:
	docker compose -f docker-compose.dev.yml down -v
	docker system prune -f --volumes

shell-backend:
	docker compose -f docker-compose.dev.yml exec fastapi sh

shell-frontend:
	docker compose -f docker-compose.dev.yml exec nextjs sh
