#!/usr/bin/env python3
"""
Create .env from .env.<env>.example if missing. Cross-platform, no external deps required.
Usage: python scripts/setup_env.py [env]
"""
import sys
from pathlib import Path
import base64
import os

env = sys.argv[1] if len(sys.argv) > 1 else "dev"
example = Path(f".env.{env}.example")
dest = Path(".env")

if dest.exists():
    print('.env はすでに存在します。スキップします。')
    sys.exit(0)

if not example.exists():
    print(f"Error: {example} が見つかりません。", file=sys.stderr)
    sys.exit(1)

# Generate Fernet-compatible key without external libs
key = base64.urlsafe_b64encode(os.urandom(32)).decode()

text = example.read_text(encoding='utf-8')
new_lines = []
replaced = False
for line in text.splitlines():
    if line.startswith('ENCRYPTION_KEY='):
        new_lines.append(f'ENCRYPTION_KEY={key}')
        replaced = True
    else:
        new_lines.append(line)

if not replaced:
    # Append at end if no ENCRYPTION_KEY line
    new_lines.append(f'ENCRYPTION_KEY={key}')

dest.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
print(f'.env を {example} から作成しました。ENCRYPTION_KEY を埋めました。')
print('GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET / JWT_SECRET を必要に応じて .env に設定してください。')
