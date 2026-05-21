# Vallog — 技術スタック

## 確定スタック

| レイヤー | 技術 | 選定理由 |
|---|---|---|
| フロントエンド | Next.js | Cloudflare Tunnel前提で同一オリジン構成が活きる・SSRをダッシュボード初期取得に活用できる |
| バックエンド | FastAPI | Venduce実績あり |
| DB | PostgreSQL | Venduce実績あり |
| 認証 | GitHub OAuthのみ | ログイン手段はGitHub一本 |
| トークン管理 | アクセストークン（メモリ保持）+ リフレッシュトークン（HttpOnly Cookie） | XSS耐性とモバイル拡張性を両立するベストプラクティス |
| インフラ | Docker Compose + Cloudflare Tunnel | 環境再現性・チーム参入コストの低さ・Venduceからの流用 |
| リバースプロキシ | nginx | 同一オリジン化・APIプレフィックス統一 |
| ホスティング | Proxmox上のUbuntu Server（VM1台） | Docker直よりオーバーヘッド小・チームのインフラ構成に合わせる |

---

## APIルーティング設計

バックエンドのエンドポイントは **`/api/*` に統一**し、フロント・バック間のパス衝突を構造的に防ぐ。

```
[ブラウザ]
└── https://vallog.com
    └── Cloudflare Tunnel
        └── nginx:80
            ├── /api/*  → FastAPI (uvicorn)
            └── /*      → Next.js (next start)
```

---

## 開発環境の設計方針

開発環境ではNext.js Rewritesを使って同一オリジンを再現する。

```typescript
// next.config.ts
rewrites() {
  return [{ source: '/api/:path*', destination: 'http://localhost:8000/:path*' }]
}
```

- `NEXT_PUBLIC_API_BASE_URL` は空にしてRewritesに委譲
- 開発・本番ともにブラウザからは `/api/*` への単一オリジンリクエストになる

---

## インフラ構成（VM1台構成）

```
Proxmox
└── VM: Ubuntu Server
    └── docker compose up
        ├── nginx
        ├── Next.js (next start)
        ├── FastAPI (uvicorn)
        ├── PostgreSQL
        └── cloudflared（本番のみ・profiles: production）
```

VM1台にまとめる理由: SSH接続先が増えることによる運用コストを避けるため。DBのスナップショットはVM全体のProxmoxスナップショットで代替する。
