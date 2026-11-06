"""Create the v1 tables.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "blobs",
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("sha256"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("handle", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("handle"),
    )
    op.create_table(
        "changes",
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("ref", sa.Text(), nullable=False),
        sa.Column("op", sa.String(length=8), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("seq"),
    )
    with op.batch_alter_table("changes", schema=None) as batch_op:
        batch_op.create_index("ix_changes_run_seq", ["run_id", "seq"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.String(length=64), nullable=True),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_jobs_run_id"), ["run_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_jobs_updated_at"), ["updated_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_jobs_user_id"), ["user_id"], unique=False)

    op.create_table(
        "machines",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.String(length=64), nullable=True),
        sa.Column("slug", sa.String(length=200), nullable=True),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("benchmark", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("has_holding", sa.Boolean(), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_runs_ticker"), ["ticker"], unique=False)
        batch_op.create_index(batch_op.f("ix_runs_user_id"), ["user_id"], unique=False)

    op.create_table(
        "start_overs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("start_overs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_start_overs_user_id"), ["user_id"], unique=False)

    op.create_table(
        "tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("scopes", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_table(
        "watchlist",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "ticker"),
    )
    op.create_table(
        "artifacts",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=200), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=200), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.ForeignKeyConstraint(["sha256"], ["blobs.sha256"]),
        sa.PrimaryKeyConstraint("run_id", "path"),
    )
    op.create_table(
        "calls",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("n", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.ForeignKeyConstraint(["sha256"], ["blobs.sha256"]),
        sa.PrimaryKeyConstraint("run_id", "n"),
    )
    op.create_table(
        "followups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("followups", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_followups_run_id"), ["run_id"], unique=False)

    op.create_table(
        "reflections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("reflections", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_reflections_run_id"), ["run_id"], unique=False)

    op.create_table(
        "rulings",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("ruled_at", sa.DateTime(), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("probability", sa.Double(), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=True),
        sa.Column("target_low", sa.Double(), nullable=False),
        sa.Column("target_likely", sa.Double(), nullable=False),
        sa.Column("target_high", sa.Double(), nullable=False),
        sa.Column("check_date", sa.String(length=10), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("reference_date", sa.String(length=10), nullable=True),
        sa.Column("reference_close", sa.Double(), nullable=True),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("run_id"),
    )
    with op.batch_alter_table("rulings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_rulings_model"), ["model"], unique=False)
        batch_op.create_index(batch_op.f("ix_rulings_ruled_at"), ["ruled_at"], unique=False)

    op.create_table(
        "settlements",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("settled_at", sa.DateTime(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_table(
        "standings",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("as_of", sa.String(length=10), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("run_id", "as_of"),
    )


def downgrade() -> None:
    op.drop_table("standings")
    op.drop_table("settlements")
    with op.batch_alter_table("rulings", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_rulings_ruled_at"))
        batch_op.drop_index(batch_op.f("ix_rulings_model"))

    op.drop_table("rulings")
    with op.batch_alter_table("reflections", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_reflections_run_id"))

    op.drop_table("reflections")
    with op.batch_alter_table("followups", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_followups_run_id"))

    op.drop_table("followups")
    op.drop_table("calls")
    op.drop_table("artifacts")
    op.drop_table("watchlist")
    op.drop_table("tokens")
    with op.batch_alter_table("start_overs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_start_overs_user_id"))

    op.drop_table("start_overs")
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_runs_user_id"))
        batch_op.drop_index(batch_op.f("ix_runs_ticker"))

    op.drop_table("runs")
    op.drop_table("machines")
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_jobs_user_id"))
        batch_op.drop_index(batch_op.f("ix_jobs_updated_at"))
        batch_op.drop_index(batch_op.f("ix_jobs_run_id"))

    op.drop_table("jobs")
    with op.batch_alter_table("changes", schema=None) as batch_op:
        batch_op.drop_index("ix_changes_run_seq")

    op.drop_table("changes")
    op.drop_table("users")
    op.drop_table("blobs")
