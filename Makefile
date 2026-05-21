.PHONY: up down dev dev-build dev-down build logs ps clean migrate migrate-create shell-backend shell-db

# ---------- 本番 ----------
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build --no-cache

logs:
	docker compose logs -f

ps:
	docker compose ps

# ---------- 開発 ----------
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

dev-build:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache

dev-down:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

# ---------- DB ----------
migrate:
	@if [ -f alembic.ini ] && [ -d migrations ]; then \
		docker compose exec backend alembic upgrade head; \
	else \
		echo "Error: Alembic is not configured for this repository (missing alembic.ini and/or migrations directory)."; \
		echo "Add the Alembic configuration/migration scaffolding before running 'make migrate'."; \
		exit 1; \
	fi

migrate-create:
	@if [ -f alembic.ini ] && [ -d migrations ]; then \
		docker compose exec backend alembic revision --autogenerate -m "$(msg)"; \
	else \
		echo "Error: Alembic is not configured for this repository (missing alembic.ini and/or migrations directory)."; \
		echo "Add the Alembic configuration/migration scaffolding before running 'make migrate-create msg=\"...\"'."; \
		exit 1; \
	fi

# ---------- シェル ----------
shell-backend:
	docker compose exec backend bash

shell-db:
	docker compose exec db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

# ---------- クリーンアップ ----------
clean:
	docker compose down -v --rmi local
