import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql

from app.repositories.distribution import DistributionRepository, unfinalized_exists_query


def test_unfinalized_gate_query_contains_all_disclosure_predicates():
    query = unfinalized_exists_query(
        uuid.uuid4(), datetime(2026, 8, 1, tzinfo=timezone.utc)
    )
    sql = str(
        query.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    ).lower()

    assert "distribution_proposals.finalized is false" in sql
    assert "distribution_proposals.deleted_at is null" in sql
    assert "greatest(distribution_proposals.created_at, coalesce(" in sql
    assert "max(distribution_edit_logs.created_at)" in sql


async def test_get_proposal_adds_for_update_when_requested():
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)

    await DistributionRepository(db).get_proposal(uuid.uuid4(), for_update=True)

    query = db.scalar.await_args.args[0]
    sql = str(query.compile(dialect=postgresql.dialect())).lower()
    assert "for update" in sql


async def test_list_proposals_counts_only_logs_that_changed_allocations():
    rows = MagicMock()
    rows.all.return_value = []
    db = MagicMock()
    db.scalars = AsyncMock(return_value=rows)

    await DistributionRepository(db).list_proposals(uuid.uuid4())

    query = db.scalars.await_args.args[0]
    sql = str(query.compile(dialect=postgresql.dialect())).lower()
    assert "count(distribution_edit_logs.id)" in sql
    assert "distribution_edit_logs.before_items ->" in sql
    assert "!= (distribution_edit_logs.after_items ->" in sql
