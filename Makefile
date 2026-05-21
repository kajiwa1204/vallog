.PHONY: up down dev build logs ps clean migrate shell-backend shell-db

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
	docker compose exec backend alembic upgrade head

migrate-create:
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

# ---------- シェル ----------
shell-backend:
	docker compose exec backend bash

shell-db:
	docker compose exec db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

# ---------- クリーンアップ ----------
clean:
	docker compose down -v --rmi local
