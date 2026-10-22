"""Customer-scoped native PeopleWelcome connections and durable chat submissions."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("peoplewelcome_connections",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(256), nullable=False),
        sa.Column("credential", sa.Text(), nullable=False),
        sa.Column("ai_id", sa.String(128), nullable=False),
        sa.Column("ai_name", sa.String(256), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="peoplewelcome_account_owner"))
    op.create_table("assistant_turns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("ai_id", sa.String(128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("baseline", sa.JSON(), nullable=False),
        sa.Column("job_id", sa.String(128)),
        sa.Column("conversation_id", sa.String(128)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("replies", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "key", name="assistant_idempotency"))
    op.create_index("ix_assistant_turns_user_id", "assistant_turns", ["user_id"])


def downgrade():
    op.drop_table("assistant_turns")
    op.drop_table("peoplewelcome_connections")
