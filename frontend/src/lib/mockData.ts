import type {
  ContributionSummary,
  DistributionProposal,
  Member,
  MemberScore,
  Project,
  Weight,
} from "@/types";

export const mockProjects: Project[] = [
  {
    id: "vallog",
    name: "Vallog",
    description: "貢献可視化・報酬分配ツール",
    repository: "kajiwa1204/vallog",
    memberCount: 4,
    updatedAt: "2026-06-03T10:23:00Z",
    totalReward: 300000,
  },
  {
    id: "hackathon-2026",
    name: "Hackathon 2026 Demo",
    description: "学内ハッカソンの応募作品",
    repository: "team-alpha/hackathon-2026",
    memberCount: 5,
    updatedAt: "2026-05-21T18:01:00Z",
    totalReward: 100000,
  },
];

export const mockMembers: Member[] = [
  {
    login: "kajiwa1204",
    name: "Kajiwara",
    avatarUrl: "https://avatars.githubusercontent.com/u/195684218?v=4",
    role: "owner",
  },
  {
    login: "shou6439",
    name: "Kameda Masato",
    avatarUrl: "https://avatars.githubusercontent.com/u/82638006?v=4",
    role: "member",
  },
  {
    login: "yozure420",
    name: "Yozure",
    avatarUrl: "https://avatars.githubusercontent.com/u/100000003?v=4",
    role: "member",
  },
  {
    login: "miyamoto",
    name: "Miyamoto",
    avatarUrl: "https://avatars.githubusercontent.com/u/100000004?v=4",
    role: "member",
  },
];

export const mockScores: MemberScore[] = [
  {
    login: "kajiwa1204",
    name: "Kajiwara",
    avatarUrl: "https://avatars.githubusercontent.com/u/195684218?v=4",
    total: 312,
    breakdown: { issue: 48, pr: 130, review: 64, tat: 30, sp: 40 },
    counts: { issuesClosed: 12, prsMerged: 18, reviewsGiven: 24, avgTatHours: 7.2, spTotal: 40 },
  },
  {
    login: "shou6439",
    name: "Kameda Masato",
    avatarUrl: "https://avatars.githubusercontent.com/u/82638006?v=4",
    total: 268,
    breakdown: { issue: 32, pr: 112, review: 58, tat: 28, sp: 38 },
    counts: { issuesClosed: 8, prsMerged: 16, reviewsGiven: 22, avgTatHours: 8.4, spTotal: 38 },
  },
  {
    login: "yozure420",
    name: "Yozure",
    avatarUrl: "https://avatars.githubusercontent.com/u/100000003?v=4",
    total: 198,
    breakdown: { issue: 28, pr: 84, review: 40, tat: 22, sp: 24 },
    counts: { issuesClosed: 7, prsMerged: 12, reviewsGiven: 15, avgTatHours: 10.1, spTotal: 24 },
  },
  {
    login: "miyamoto",
    name: "Miyamoto",
    avatarUrl: "https://avatars.githubusercontent.com/u/100000004?v=4",
    total: 142,
    breakdown: { issue: 20, pr: 60, review: 30, tat: 18, sp: 14 },
    counts: { issuesClosed: 5, prsMerged: 9, reviewsGiven: 11, avgTatHours: 12.5, spTotal: 14 },
  },
];

export const defaultWeights: Weight = {
  issue: 1.0,
  pr: 2.0,
  review: 1.5,
  tat: 1.0,
  sp: 1.0,
};

export const mockSummaries: Record<string, ContributionSummary> = {
  kajiwa1204: {
    login: "kajiwa1204",
    summary:
      "バックエンド基盤の整備をリードした。FastAPIのセットアップ、Alembicマイグレーション、認証周りのセキュリティ対応（GitHubアクセストークンのFernet暗号化）を担当し、開発環境の土台を作り上げた。レビュー数も最多で、他メンバーのPRに対する設計面の指摘を一貫して行っている。",
    highlights: [
      "FastAPI/Alembicの初期セットアップを単独で構築",
      "認証情報暗号化のセキュリティ実装をリード",
      "全PRに対する設計レビューを担当",
    ],
    items: [
      {
        type: "pr",
        title: "feat(backend): setup FastAPI",
        url: "https://github.com/kajiwa1204/vallog/pull/23",
        mergedAt: "2026-06-04T03:09:00Z",
        number: 23,
      },
      {
        type: "pr",
        title: "feat: Alembic初期セットアップとusersテーブルのマイグレーション",
        url: "https://github.com/kajiwa1204/vallog/pull/21",
        mergedAt: "2026-06-04T07:09:00Z",
        number: 21,
      },
      {
        type: "review",
        title: "Review on #22 Next.jsフロントエンドの初期セットアップ",
        url: "https://github.com/kajiwa1204/vallog/pull/22",
        number: 22,
      },
    ],
  },
  shou6439: {
    login: "shou6439",
    summary:
      "プロダクトの方向性とドキュメント整備をリードした。バリュー・ミッション・MVPスコープなどプロダクトコアの文書化を担当。開発フロー整備にも貢献し、Issue管理ルール・ブランチ命名規則を導入した。",
    highlights: [
      "プロダクト概要・MVPスコープの初版を作成",
      "Issue管理・ブランチ命名ルールを導入",
      "Makefile整備・dev/prod共通化",
    ],
    items: [
      {
        type: "pr",
        title: "docs: 詳細的な開発フローをREADMEに追加",
        url: "https://github.com/kajiwa1204/vallog/pull/20",
        mergedAt: "2026-06-03T18:00:00Z",
        number: 20,
      },
      {
        type: "pr",
        title: "chore: Makefileをdev/prod共通化",
        url: "https://github.com/kajiwa1204/vallog/pull/15",
        mergedAt: "2026-06-02T17:24:00Z",
        number: 15,
      },
    ],
  },
  yozure420: {
    login: "yozure420",
    summary:
      "フロントエンド側の初期セットアップを担当。Next.js App Routerでのページ構成、APIクライアントの基礎を構築した。ディレクトリ構成の議論にも積極的に参加し、featuresベースのフラット構成を提案・採用した。",
    highlights: [
      "Next.js App Routerでのフロントエンド土台を構築",
      "ディレクトリ構成（featuresフラット）を提案",
      "APIクライアントの fetch wrapper を実装",
    ],
    items: [
      {
        type: "pr",
        title: "feat: Next.jsフロントエンドの初期セットアップ",
        url: "https://github.com/kajiwa1204/vallog/pull/22",
        mergedAt: "2026-06-04T01:36:00Z",
        number: 22,
      },
    ],
  },
  miyamoto: {
    login: "miyamoto",
    summary:
      "Docker構成・nginxリバースプロキシ・Cloudflare Tunnelなどインフラ周りを担当。dev/prod環境分離の方針作成とDockerfileの最適化を実施した。",
    highlights: [
      "Docker Compose + nginx + Cloudflare Tunnel構成を整備",
      "Dockerfileのslim化・実行順序の最適化",
    ],
    items: [
      {
        type: "pr",
        title: "fix(dockerfile): Pythonのバージョンを3.13.13に変更",
        url: "https://github.com/kajiwa1204/vallog/pull/2",
        mergedAt: "2026-05-30T11:00:00Z",
        number: 2,
      },
    ],
  },
};

export const computeDistribution = (
  totalReward: number,
  weights: Weight,
  scores: MemberScore[],
): DistributionProposal => {
  const adjustedScores = scores.map((s) => {
    const adjusted =
      s.breakdown.issue * weights.issue +
      s.breakdown.pr * weights.pr +
      s.breakdown.review * weights.review +
      s.breakdown.tat * weights.tat +
      s.breakdown.sp * weights.sp;
    return { ...s, adjusted };
  });
  const totalScore = adjustedScores.reduce((acc, s) => acc + s.adjusted, 0);
  const items = adjustedScores.map((s) => {
    const ratio = totalScore > 0 ? s.adjusted / totalScore : 0;
    return {
      login: s.login,
      name: s.name,
      avatarUrl: s.avatarUrl,
      score: Math.round(s.adjusted * 10) / 10,
      ratio,
      amount: Math.round(totalReward * ratio),
    };
  });
  return {
    id: "preview",
    name: "現在のプレビュー",
    totalReward,
    weights,
    items,
    createdAt: new Date().toISOString(),
  };
};

export const formatYen = (value: number) =>
  new Intl.NumberFormat("ja-JP", { style: "currency", currency: "JPY", maximumFractionDigits: 0 }).format(value);
