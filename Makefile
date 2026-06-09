.PHONY: setup install up down build logs ps clean migrate migrate-create shell-db shell-backend

ENV ?= dev

ifeq ($(ENV), prod)
  DC = docker compose --env-file .env
else
  DC = docker compose --env-file .env -f docker-compose.yml -f docker-compose.dev.yml
endif

# ---------- 初回セットアップ ----------
setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		KEY=$$(docker run --rm python:3.11-slim sh -c "pip install -q cryptography 2>/dev/null && python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"); \
		awk -v key="$$KEY" '/^ENCRYPTION_KEY=/{print "ENCRYPTION_KEY=" key; next}1' .env > .env.tmp && mv .env.tmp .env; \
		echo ".env を作成しました。GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET / JWT_SECRET を設定してください。"; \
	else \
		echo ".env はすでに存在します。スキップします。"; \
	fi
	$(MAKE) install
	$(MAKE) build

# コンテナと同じ Node バージョンで pnpm install を実行し、node_modules をローカルに生成する。
# ローカルの Node バージョンに依存せず、IDE の型補完が正しく動く状態を作るのが目的。
# アプリの実行はコンテナで行うため、ネイティブアドオン（sharp 等）のバイナリ差異は問題にならない。
install:
	docker run --rm -v $(PWD)/frontend:/app -w /app node:22-alpine sh -c "corepack enable pnpm && pnpm install"

# ---------- 起動 / 停止 ----------
up:
	$(DC) up -d

down:
	$(DC) down

build:
	$(DC) build --no-cache

logs:
	$(DC) logs -f

ps:
	docker compose --env-file .env ps

# ---------- 開発 ----------
dev:
	docker compose --env-file .env -f docker-compose.yml -f docker-compose.dev.yml up

dev-build:
	docker compose --env-file .env -f docker-compose.yml -f docker-compose.dev.yml build --no-cache

dev-down:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env down
	$(DC) ps

clean:
	$(DC) down -v --rmi local

# ---------- マイグレーション ----------
ifeq ($(ENV), prod)
migrate:
	$(DC) exec backend alembic upgrade head

migrate-create:
	@if [ -z "$(msg)" ]; then echo "Usage: make migrate-create msg=\"migration name\""; exit 1; fi
	$(DC) exec backend alembic revision --autogenerate -m "$(msg)"
else
migrate:
	@if [ ! -f .env ]; then echo "Error: .env が見つかりません。まず make setup を実行してください。"; exit 1; fi
	set -a && . .env && set +a && cd backend && alembic upgrade head

migrate-create:
	@if [ ! -f .env ]; then echo "Error: .env が見つかりません。まず make setup を実行してください。"; exit 1; fi
	@if [ -z "$(msg)" ]; then echo "Usage: make migrate-create msg=\"migration name\""; exit 1; fi
	set -a && . .env && set +a && cd backend && alembic revision --autogenerate -m "$(msg)"
endif

# ---------- シェル ----------
shell-db:
	$(DC) exec db sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'

shell-backend:
	$(DC) exec backend bash
