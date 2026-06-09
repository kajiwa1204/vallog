export type Project = {
  id: string;
  name: string;
  description: string;
  repository: string;
  memberCount: number;
  updatedAt: string;
  totalReward: number;
};

export type Member = {
  login: string;
  name: string;
  avatarUrl: string;
  role: "owner" | "member";
};

export type ScoreCategory = "issue" | "pr" | "review" | "tat" | "sp";

export type MemberScore = {
  login: string;
  name: string;
  avatarUrl: string;
  total: number;
  breakdown: Record<ScoreCategory, number>;
  counts: {
    issuesClosed: number;
    prsMerged: number;
    reviewsGiven: number;
    avgTatHours: number;
    spTotal: number;
  };
};

export type ContributionItem = {
  type: "pr" | "issue" | "review";
  title: string;
  url: string;
  mergedAt?: string;
  number: number;
};

export type ContributionSummary = {
  login: string;
  summary: string;
  highlights: string[];
  items: ContributionItem[];
};

export type Weight = Record<ScoreCategory, number>;

export type DistributionItem = {
  login: string;
  name: string;
  avatarUrl: string;
  score: number;
  ratio: number;
  amount: number;
  manualOverride?: number;
};

export type DistributionProposal = {
  id: string;
  name: string;
  totalReward: number;
  weights: Weight;
  items: DistributionItem[];
  createdAt: string;
};
