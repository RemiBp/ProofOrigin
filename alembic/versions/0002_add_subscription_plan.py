"""Add subscription_plan column to users."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_add_subscription_plan"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("subscription_plan", sa.String(length=32), nullable=True),
    )
    op.execute(
        "UPDATE users SET subscription_plan='free' WHERE subscription_plan IS NULL"
    )
    op.alter_column("users", "subscription_plan", nullable=False, server_default="free")


def downgrade() -> None:
    op.drop_column("users", "subscription_plan")
