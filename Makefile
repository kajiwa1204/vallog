.PHONY: setup install up down build logs ps clean migrate migrate-create shell-db shell-backend

ENV ?= dev
ENV_EXAMPLE = .env.$(ENV).example

# 本番は cloudflared が profiles: [production] にいるため、プロファイルを指定しないと
# トンネルが起動せず公開されない。down でも対象から漏れ、切り戻したつもりで公開だけ
# 残るため、DC 自体に持たせて up/down/logs/ps/clean すべてで揃える。
# dev 側には付けないこと（docker-compose.dev.yml が nginx にも同じプロファイルを
# 付けており、dev で不要な nginx まで起動する）
ifeq ($(ENV), prod)
	DC = docker compose --env-file .env --profile production
else
	DC = docker compose --env-file .env -f docker-compose.yml -f docker-compose.dev.yml
endif

ifeq ($(OS),Windows_NT)
	PYTHON ?= py
else
	PYTHON ?= python3
endif

ifdef MSYSTEM
DOCKER_NO_PATHCONV = MSYS_NO_PATHCONV=1
else
DOCKER_NO_PATHCONV =
endif

# ---------- 初回セットアップ ----------
setup:
	$(PYTHON) scripts/setup_env.py $(ENV)
	$(MAKE) install
	$(MAKE) build

# コンテナと同じ Node バージョンで pnpm install を実行し、node_modules をローカルに生成する。
# ローカルの Node バージョンに依存せず、IDE の型補完が正しく動く状態を作るのが目的。
# アプリの実行はコンテナで行うため、ネイティブアドオン（sharp 等）のバイナリ差異は問題にならない。
install:
	$(DOCKER_NO_PATHCONV) docker run --rm -v $(CURDIR)/frontend:/app -w /app node:22-alpine sh -c "corepack enable pnpm && pnpm install --frozen-lockfile"

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
# dev / prod ともコンテナ内で実行する。DATABASE_URL のホスト名 `db` は Compose
# ネットワーク内でしか解決できないため、ホストで alembic を叩くと必ず接続に失敗する。
# 先に make dev（または make up）でコンテナを起動しておくこと
migrate:
	$(DC) exec backend alembic upgrade head

migrate-create:
	@if [ -z "$(msg)" ]; then echo "Usage: make migrate-create msg=\"migration name\""; exit 1; fi
	$(DC) exec backend alembic revision --autogenerate -m "$(msg)"

# ---------- シェル ----------
shell-db:
	$(DC) exec db sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'

shell-backend:
	$(DC) exec backend bash
