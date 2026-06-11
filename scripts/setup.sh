#!/bin/sh
set -e

ENV_EXAMPLE="$1"

if [ ! -f .env ]; then
    if [ ! -f "$ENV_EXAMPLE" ]; then
        echo "Error: $ENV_EXAMPLE が見つかりません。"
        exit 1
    fi
    KEY=$(docker run --rm python:3.11-slim sh -c \
        "pip install -q cryptography 2>/dev/null && \
         python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
    awk -v key="$KEY" '/^ENCRYPTION_KEY=/{print "ENCRYPTION_KEY=" key; next}1' "$ENV_EXAMPLE" > .env
    echo ".env を $ENV_EXAMPLE から作成しました。GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET / JWT_SECRET を設定してください。"
else
    echo ".env はすでに存在します。スキップします。"
fi
