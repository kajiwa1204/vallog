# Windows: BusyBox sh (Scoop) は CP932 でスクリプトを読むため UTF-8 の日本語が文字化けする。
# git --exec-path を起点に Git for Windows の sh.exe (UTF-8 対応) を検出して使う。
ifeq ($(OS),Windows_NT)
  _git_exec := $(shell git --exec-path 2>nul)
  ifneq ($(_git_exec),)
    _git_root := $(shell echo $(_git_exec) | sed 's|/[^/]*/[^/]*/[^/]*$$||')
    SHELL := $(_git_root)/usr/bin/sh.exe
  else
    SHELL := sh
  endif
else
  SHELL := /bin/sh
endif

.PHONY: setup install up down build logs ps clean migrate migrate-create shell-db shell-backend

ENV ?= dev
ENV_EXAMPLE = .env.$(ENV).example

ifeq ($(ENV), prod)
  DC = docker compose --env-file .env
else
  DC = docker compose --env-file .env -f docker-compose.yml -f docker-compose.dev.yml
endif

# ---------- 初回セットアップ ----------
setup:
	@"$(SHELL)" scripts/setup.sh $(ENV_EXAMPLE)
	$(MAKE) install
	$(MAKE) build

# コンテナと同じ Node バージョンで pnpm install を実行し、node_modules をローカルに生成する。
# ローカルの Node バージョンに依存せず、IDE の型補完が正しく動く状態を作るのが目的。
# アプリの実行はコンテナで行うため、ネイティブアドオン（sharp 等）のバイナリ差異は問題にならない。
install:
	docker run --rm -v $(PWD)/frontend:/app -w /app node:22-alpine sh -c "corepack enable pnpm && pnpm install --frozen-lockfile"

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
	@if [ -z "$(msg)" ]; then echo "使い方: make migrate-create msg=\"マイグレーション名\""; exit 1; fi
	$(DC) exec backend alembic revision --autogenerate -m "$(msg)"
else
migrate:
	@if [ ! -f .env ]; then echo "エラー: .env が見つかりません。先に make setup を実行してください。"; exit 1; fi
	set -a && . .env && set +a && cd backend && alembic upgrade head

migrate-create:
	@if [ ! -f .env ]; then echo "エラー: .env が見つかりません。先に make setup を実行してください。"; exit 1; fi
	@if [ -z "$(msg)" ]; then echo "使い方: make migrate-create msg=\"マイグレーション名\""; exit 1; fi
	set -a && . .env && set +a && cd backend && alembic revision --autogenerate -m "$(msg)"
endif

# ---------- シェル ----------
shell-db:
	$(DC) exec db sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'

shell-backend:
	$(DC) exec backend bash
