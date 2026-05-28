"""
Add needs_review column to transactions table.

Revision ID: 001_add_needs_review
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_add_needs_review'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add needs_review column to transactions table
    op.add_column('transactions', sa.Column('needs_review', sa.Boolean(), nullable=True, server_default='0'))

    # Create index for efficient filtering
    op.create_index('idx_transactions_needs_review', 'transactions', ['needs_review'])
    op.create_index('idx_transactions_client_review', 'transactions', ['client_id', 'needs_review'])


def downgrade() -> None:
    # Drop index first
    op.drop_index('idx_transactions_client_review', table_name='transactions')
    op.drop_index('idx_transactions_needs_review', table_name='transactions')

    # Drop column
    op.drop_column('transactions', 'needs_review')
