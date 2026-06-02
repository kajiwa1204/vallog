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
		echo ".env を作成しました。GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET / JWT_SECRET を設定してください。"; \
	else \
		echo ".env はすでに存在します。スキップします。"; \
	fi
	$(MAKE) install
	$(MAKE) build

# コンテナと同じ Node バージョンで npm install を実行し、node_modules をローカルに生成する。
# ローカルの Node バージョンに依存せず、IDE の型補完が正しく動く状態を作るのが目的。
# アプリの実行はコンテナで行うため、ネイティブアドオン（sharp 等）のバイナリ差異は問題にならない。
install:
	docker run --rm -v $(PWD)/frontend:/app -w /app node:22-alpine npm install

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
	set -a && . .env && set +a && cd backend && alembic upgrade head

migrate-create:
	@if [ -z "$(msg)" ]; then echo "Usage: make migrate-create msg=\"migration name\""; exit 1; fi
	set -a && . .env && set +a && cd backend && alembic revision --autogenerate -m "$(msg)"
endif

# ---------- シェル ----------
shell-db:
	$(DC) exec db psql -U vallog -d vallog_db

shell-backend:
	$(DC) exec backend bash
