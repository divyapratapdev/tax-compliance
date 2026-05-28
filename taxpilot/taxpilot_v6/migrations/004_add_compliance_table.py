"""004_add_compliance_table

Adds:  compliance_items
"""

from alembic import op
import sqlalchemy as sa


revision  = "004"
down_revision = "003"
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        "compliance_items",
        sa.Column("id",           sa.String(36),  primary_key=True),
        sa.Column("client_id",    sa.Integer(),   sa.ForeignKey("clients.id"), nullable=False),

        sa.Column("type",         sa.String(30),  nullable=False),
        sa.Column("due_date",     sa.DateTime(),  nullable=False),
        sa.Column("period_month", sa.Integer(),   nullable=True),
        sa.Column("period_year",  sa.Integer(),   nullable=True),
        sa.Column("quarter",      sa.String(2),   nullable=True),
        sa.Column("description",  sa.String(255), nullable=True),

        sa.Column("status",       sa.String(20),  server_default="pending"),
        sa.Column("filed_at",     sa.DateTime(),  nullable=True),
        sa.Column("filed_by",     sa.String(100), nullable=True),

        sa.Column("reminder_7day_sent", sa.Boolean(), server_default="0"),
        sa.Column("reminder_1day_sent", sa.Boolean(), server_default="0"),
        sa.Column("escalation_sent",    sa.Boolean(), server_default="0"),

        sa.Column("penalty_per_day",     sa.Float(),  server_default="0"),
        sa.Column("penalty_description", sa.Text(),   nullable=True),

        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )

    op.create_index("idx_ci_client_status", "compliance_items", ["client_id", "status"])
    op.create_index("idx_ci_client_due",    "compliance_items", ["client_id", "due_date"])
    op.create_index("idx_ci_client_type",   "compliance_items", ["client_id", "type"])
    op.create_index("idx_ci_reminders",     "compliance_items",
                    ["status", "reminder_7day_sent", "due_date"])


def downgrade():
    op.drop_index("idx_ci_reminders",     table_name="compliance_items")
    op.drop_index("idx_ci_client_type",   table_name="compliance_items")
    op.drop_index("idx_ci_client_due",    table_name="compliance_items")
    op.drop_index("idx_ci_client_status", table_name="compliance_items")
    op.drop_table("compliance_items")
