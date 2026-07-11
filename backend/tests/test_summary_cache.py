"""services/summary.py の2層キャッシュ再生成判定のユニットテスト。

Tier 1: head_sha（+ title/body/レビュー/モデル）が変わった場合のみ再生成する。
Tier 2: Tier 1の内容が変わった場合のみ再生成する。
LLM・GitHub API・DBは使わない。
"""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError, ErrorCode
from app.models import (
    GitHubIssue,
    GitHubPullRequest,
    GitHubReview,
    PRSummary,
    SummaryJob,
)
from app.services.summary import (
    _PR_BODY_CHAR_LIMIT,
    _trim_diff,
    enqueue_summary_job,
    member_context_hash,
    pr_context_hash,
    select_prs_to_generate,
)

_PREFIX = "claude:claude-haiku-4-5-20251001"


def _pr(number: int = 1, head_sha: str = "abc123", **overrides) -> GitHubPullRequest:
    defaults = dict(
        project_id=uuid.uuid4(),
        github_id=number,
        number=number,
        title=f"PR {number}",
        body="本文",
        head_sha=head_sha,
        author_login="alice",
        state="closed",
        draft=False,
        html_url=f"https://github.com/o/r/pull/{number}",
        gh_created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        merged_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
        closed_at=None,
        reopened_count=0,
    )
    defaults.update(overrides)
    return GitHubPullRequest(**defaults)


def _review(
    pr_number: int, body: str = "LGTM", reviewer_login: str = "bob"
) -> GitHubReview:
    return GitHubReview(
        project_id=uuid.uuid4(),
        github_id=hash((pr_number, body, reviewer_login)) % 10**9,
        pr_number=pr_number,
        reviewer_login=reviewer_login,
        state="APPROVED",
        body=body,
        comment_count=0,
        html_url="https://github.com/o/r/pull/1#review",
        submitted_at=None,
    )


def _summary(pr_number: int, context_hash: str, content: str = "要約") -> PRSummary:
    return PRSummary(
        project_id=uuid.uuid4(),
        pr_number=pr_number,
        author_login="alice",
        content=content,
        context_hash=context_hash,
    )


def _issue(
    number: int = 1,
    author_login: str = "alice",
    state: str = "open",
    title: str = "Issue",
    labels: list[str] | None = None,
) -> GitHubIssue:
    return GitHubIssue(
        project_id=uuid.uuid4(),
        github_id=number,
        number=number,
        title=title,
        author_login=author_login,
        state=state,
        labels=labels or [],
        story_points=None,
        html_url=f"https://github.com/o/r/issues/{number}",
        gh_created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        closed_at=None,
    )


# ---------------------------------------------------------------------------
# pr_context_hash (Tier 1)
# ---------------------------------------------------------------------------

def test_pr_context_hash_is_stable_for_same_input():
    pr = _pr()
    assert pr_context_hash(pr, [], _PREFIX) == pr_context_hash(pr, [], _PREFIX)


def test_pr_context_hash_changes_when_head_sha_changes():
    before = pr_context_hash(_pr(head_sha="abc123"), [], _PREFIX)
    after = pr_context_hash(_pr(head_sha="def456"), [], _PREFIX)
    assert before != after


def test_pr_context_hash_changes_when_review_added():
    pr = _pr()
    without = pr_context_hash(pr, [], _PREFIX)
    with_review = pr_context_hash(pr, [_review(pr.number)], _PREFIX)
    assert without != with_review


def test_pr_context_hash_ignores_reviews_of_other_prs():
    pr = _pr(number=1)
    base = pr_context_hash(pr, [], _PREFIX)
    other = pr_context_hash(pr, [_review(pr_number=99)], _PREFIX)
    assert base == other


def test_pr_context_hash_changes_when_model_changes():
    pr = _pr()
    assert pr_context_hash(pr, [], "claude:model-a") != pr_context_hash(
        pr, [], "claude:model-b"
    )


def test_pr_context_hash_ignores_body_changes_beyond_generation_limit():
    # 本文の先頭 _PR_BODY_CHAR_LIMIT 字までしかLLMに渡さない（build_pr_context）ので、
    # それ以降だけ変わってもLLM出力は同一。ハッシュも変わらず再生成（＝再課金）しない
    head = "x" * _PR_BODY_CHAR_LIMIT
    base = pr_context_hash(_pr(body=head + "AAA"), [], _PREFIX)
    tail_changed = pr_context_hash(_pr(body=head + "BBB"), [], _PREFIX)
    assert base == tail_changed


def test_pr_context_hash_changes_when_body_changes_within_generation_limit():
    within = pr_context_hash(_pr(body="original body"), [], _PREFIX)
    changed = pr_context_hash(_pr(body="edited body"), [], _PREFIX)
    assert within != changed


def test_pr_context_hash_is_stable_under_review_reordering():
    # レビューのDB返却順が不定でも（submitted_atがNULL可）ハッシュは揺れない
    pr = _pr(number=1)
    r1 = _review(pr.number, body="A")
    r2 = _review(pr.number, body="B")
    r3 = _review(pr.number, body="C")
    assert pr_context_hash(pr, [r1, r2, r3], _PREFIX) == pr_context_hash(
        pr, [r3, r1, r2], _PREFIX
    )


# ---------------------------------------------------------------------------
# select_prs_to_generate (Tier 1 の再生成判定)
# ---------------------------------------------------------------------------

def test_select_generates_new_pr_without_summary():
    pr = _pr()
    assert select_prs_to_generate([pr], {}, [], _PREFIX) == [pr]


def test_select_skips_pr_with_matching_hash():
    pr = _pr()
    digest = pr_context_hash(pr, [], _PREFIX)
    existing = {pr.number: _summary(pr.number, digest)}
    assert select_prs_to_generate([pr], existing, [], _PREFIX) == []


def test_select_regenerates_pr_when_head_sha_changed():
    old_pr = _pr(head_sha="abc123")
    old_digest = pr_context_hash(old_pr, [], _PREFIX)
    existing = {old_pr.number: _summary(old_pr.number, old_digest)}

    new_pr = _pr(head_sha="def456")
    assert select_prs_to_generate([new_pr], existing, [], _PREFIX) == [new_pr]


def test_select_regenerates_only_changed_prs():
    unchanged = _pr(number=1, head_sha="aaa")
    changed_old = _pr(number=2, head_sha="bbb")
    existing = {
        1: _summary(1, pr_context_hash(unchanged, [], _PREFIX)),
        2: _summary(2, pr_context_hash(changed_old, [], _PREFIX)),
    }
    changed_new = _pr(number=2, head_sha="ccc")
    result = select_prs_to_generate([unchanged, changed_new], existing, [], _PREFIX)
    assert result == [changed_new]


# ---------------------------------------------------------------------------
# member_context_hash (Tier 2 の再生成判定)
# ---------------------------------------------------------------------------

def test_member_hash_is_stable_when_tier1_unchanged():
    summaries = [_summary(1, "h1", content="Aを実装"), _summary(2, "h2", content="Bを修正")]
    assert member_context_hash(
        "alice", summaries, [], [], _PREFIX
    ) == member_context_hash("alice", summaries, [], [], _PREFIX)


def test_member_hash_changes_when_tier1_content_changes():
    before = member_context_hash(
        "alice", [_summary(1, "h1", content="Aを実装")], [], [], _PREFIX
    )
    after = member_context_hash(
        "alice", [_summary(1, "h1", content="Aを改修")], [], [], _PREFIX
    )
    assert before != after


def test_member_hash_changes_when_tier1_set_changes():
    one = member_context_hash("alice", [_summary(1, "h1")], [], [], _PREFIX)
    two = member_context_hash(
        "alice", [_summary(1, "h1"), _summary(2, "h2")], [], [], _PREFIX
    )
    assert one != two


def test_member_hash_ignores_tier1_context_hash_itself():
    # Tier 2の入力はTier 1の「内容」。context_hashだけ変わっても内容が同じなら再生成しない
    before = member_context_hash(
        "alice", [_summary(1, "h1", content="同じ")], [], [], _PREFIX
    )
    after = member_context_hash(
        "alice", [_summary(1, "h2", content="同じ")], [], [], _PREFIX
    )
    assert before == after


def test_member_hash_changes_when_own_review_added():
    # build_member_context は当人の実施レビューを入力にするため、PR要約が不変でも再生成される
    summaries = [_summary(1, "h1", content="実装")]
    before = member_context_hash("alice", summaries, [], [], _PREFIX)
    after = member_context_hash(
        "alice", summaries, [], [_review(2, reviewer_login="alice")], _PREFIX
    )
    assert before != after


def test_member_hash_ignores_reviews_by_other_members():
    summaries = [_summary(1, "h1", content="実装")]
    before = member_context_hash("alice", summaries, [], [], _PREFIX)
    # bob のレビューは alice のサマリー入力ではないのでハッシュに影響しない
    after = member_context_hash(
        "alice", summaries, [], [_review(2, reviewer_login="bob")], _PREFIX
    )
    assert before == after


def test_member_hash_changes_when_own_issue_added():
    summaries = [_summary(1, "h1", content="実装")]
    before = member_context_hash("alice", summaries, [], [], _PREFIX)
    after = member_context_hash(
        "alice", summaries, [_issue(number=5, author_login="alice")], [], _PREFIX
    )
    assert before != after


def test_member_hash_ignores_issues_of_other_members():
    summaries = [_summary(1, "h1", content="実装")]
    before = member_context_hash("alice", summaries, [], [], _PREFIX)
    after = member_context_hash(
        "alice", summaries, [_issue(number=5, author_login="carol")], [], _PREFIX
    )
    assert before == after


# ---------------------------------------------------------------------------
# _trim_diff
# ---------------------------------------------------------------------------

def test_trim_diff_excludes_lockfiles():
    diff = (
        "diff --git a/src/app.py b/src/app.py\n+print('hi')\n"
        "diff --git a/package-lock.json b/package-lock.json\n+huge\n"
    )
    result = _trim_diff(diff)
    assert "src/app.py" in result
    assert "package-lock.json" not in result


def test_trim_diff_truncates_each_file_to_8000_chars():
    big_chunk = "diff --git a/src/big.py b/src/big.py\n" + "+x\n" * 20000
    result = _trim_diff(big_chunk)
    assert len(result) <= 8000


def test_trim_diff_skips_files_over_total_limit():
    # 8000字近いファイル5つで合計が pr_diff_char_limit(30000) を超える
    chunks = [
        f"diff --git a/src/f{i}.py b/src/f{i}.py\n" + "+x\n" * 2600
        for i in range(5)
    ]
    result = _trim_diff("".join(chunks))
    assert len(result) < 32000
    assert "省略" in result


# ---------------------------------------------------------------------------
# enqueue_summary_job（② 同時2リクエストでアクティブジョブが1件に収束）
# ---------------------------------------------------------------------------


class _Barrier:
    """2リクエストが「アクティブジョブなし」を同時に観測してから create に進むための
    最小バリア。asyncio.Barrier は Python 3.11+ のため自前で用意する。"""

    def __init__(self, parties: int):
        self._parties = parties
        self._count = 0
        self._event = asyncio.Event()

    async def wait(self) -> None:
        self._count += 1
        if self._count >= self._parties:
            self._event.set()
        await self._event.wait()


class _FakeDB:
    """summary_jobs の部分ユニーク制約(active member / active pr)を模した最小DB。
    active はフラッシュ済みで制約対象になっている行を表す。"""

    def __init__(self):
        self.active: list[SummaryJob] = []

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


class _RaceJobRepo:
    """TOCTOUレースを決定的に再現するフェイクリポジトリ。

    get_active の初回(create前チェック)はバリアで待ち合わせ、両リクエストが
    「アクティブなし」を観測してから create に進ませる。create は共有 _FakeDB の
    active に対して部分ユニーク制約を模擬し、既にアクティブジョブがあれば
    IntegrityError を投げる。pr_number でスコープが分かれる点も再現する。
    """

    def __init__(self, db: _FakeDB, barrier: _Barrier):
        self.db = db
        self.barrier = barrier
        self._precheck_done = False

    def _find(self, project_id, login, pr_number):
        return next(
            (
                j
                for j in self.db.active
                if j.project_id == project_id
                and j.github_login == login
                and j.pr_number == pr_number
                and j.status in ("pending", "running")
            ),
            None,
        )

    async def get_active(self, project_id, login, pr_number=None):
        found = self._find(project_id, login, pr_number)
        # 事前チェックのみバリアで待ち合わせ、事後リフェッチは即返す
        if not self._precheck_done:
            self._precheck_done = True
            await self.barrier.wait()
        return found

    async def create(self, project_id, login, pr_number=None):
        if self._find(project_id, login, pr_number) is not None:
            raise IntegrityError(
                "INSERT INTO summary_jobs", {}, Exception("duplicate active job")
            )
        job = SummaryJob(
            id=uuid.uuid4(),
            project_id=project_id,
            github_login=login,
            pr_number=pr_number,
            status="pending",
        )
        self.db.active.append(job)
        return job

    async def expire_stale(self, project_id, login, pr_number, threshold):
        # このテストでは死骸ジョブを扱わないので no-op
        return None


async def test_concurrent_enqueue_converges_to_single_active_job():
    project_id = uuid.uuid4()
    db = _FakeDB()
    barrier = _Barrier(2)

    with patch(
        "app.services.summary.SummaryJobRepository",
        lambda _session: _RaceJobRepo(db, barrier),
    ):
        results = await asyncio.gather(
            enqueue_summary_job(db, project_id, "alice"),
            enqueue_summary_job(db, project_id, "alice"),
        )

    assert sorted(created for _job, created in results) == [False, True]  # 起動は1件だけ
    assert results[0][0].id == results[1][0].id  # 両者が同じジョブを指す
    assert len(db.active) == 1  # DB上もアクティブジョブは1件に収束


async def test_concurrent_enqueue_for_distinct_prs_creates_two_jobs():
    # PR単独ジョブは pr_number でスコープが分かれるため、別ジョブとして両方起動する
    project_id = uuid.uuid4()
    db = _FakeDB()
    barrier = _Barrier(2)

    # PR単独ジョブは enqueue 時にPRの存在を同期チェックするので、キャッシュをスタブする
    cache_repo = AsyncMock()
    cache_repo.list_pull_requests.return_value = [
        _pr(number=1, author_login="alice"),
        _pr(number=2, author_login="alice"),
    ]

    with patch(
        "app.services.summary.SummaryJobRepository",
        lambda _session: _RaceJobRepo(db, barrier),
    ), patch(
        "app.services.summary.GitHubCacheRepository",
        lambda _session: cache_repo,
    ):
        results = await asyncio.gather(
            enqueue_summary_job(db, project_id, "alice", 1),
            enqueue_summary_job(db, project_id, "alice", 2),
        )

    assert sorted(created for _job, created in results) == [True, True]
    assert len({job.id for job, _created in results}) == 2
    assert len(db.active) == 2


async def test_enqueue_returns_existing_active_job_without_creating():
    # 事前チェックでアクティブジョブを見つけたら create せずそれを返す
    project_id = uuid.uuid4()
    existing = SummaryJob(
        id=uuid.uuid4(), project_id=project_id, github_login="alice", status="running"
    )
    repo = AsyncMock()
    repo.get_active.return_value = existing

    with patch("app.services.summary.SummaryJobRepository", lambda _s: repo):
        job, created = await enqueue_summary_job(AsyncMock(), project_id, "alice")

    assert created is False
    assert job is existing
    repo.create.assert_not_awaited()


async def test_enqueue_reraises_integrity_error_when_no_active_job():
    # レースでない本物の制約違反(リトライしてもアクティブジョブが現れない)は握り潰さず伝播する
    project_id = uuid.uuid4()
    repo = AsyncMock()
    repo.get_active.return_value = None  # 毎回アクティブジョブなし
    repo.create.side_effect = IntegrityError("INSERT", {}, Exception("boom"))

    db = AsyncMock()
    with patch("app.services.summary.SummaryJobRepository", lambda _s: repo):
        with pytest.raises(IntegrityError):
            await enqueue_summary_job(db, project_id, "alice")

    db.rollback.assert_awaited()


async def test_enqueue_pr_job_raises_404_when_pr_not_authored_by_member():
    # 存在しない/別人authorのPRは、ジョブを積まず同期的に404を返す（202→非同期失敗にしない）
    project_id = uuid.uuid4()
    cache_repo = AsyncMock()
    cache_repo.list_pull_requests.return_value = [_pr(number=1, author_login="bob")]

    with patch("app.services.summary.GitHubCacheRepository", lambda _s: cache_repo):
        with pytest.raises(AppError) as exc_info:
            await enqueue_summary_job(AsyncMock(), project_id, "alice", 1)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == ErrorCode.SUMMARY_PR_NOT_FOUND


async def test_enqueue_expires_stale_running_job_then_creates_new():
    # プロセス異常終了で running のまま残ったジョブは失効させ、新規ジョブを作れる
    project_id = uuid.uuid4()
    stale = SummaryJob(
        id=uuid.uuid4(),
        project_id=project_id,
        github_login="alice",
        status="running",
        pr_number=None,
    )
    repo = AsyncMock()

    def _expire(*_args, **_kwargs):
        stale.status = "failed"  # 失効を模擬（部分ユニークindexの対象から外れる）

    repo.expire_stale.side_effect = _expire
    repo.get_active.side_effect = lambda *a, **k: (
        stale if stale.status in ("pending", "running") else None
    )
    new_job = SummaryJob(
        id=uuid.uuid4(),
        project_id=project_id,
        github_login="alice",
        status="pending",
    )
    repo.create.return_value = new_job

    with patch("app.services.summary.SummaryJobRepository", lambda _s: repo):
        job, created = await enqueue_summary_job(AsyncMock(), project_id, "alice")

    repo.expire_stale.assert_awaited()
    assert created is True
    assert job is new_job
