"""
Add TDS computation tables.

Revision ID: 003_add_tds_tables
Revises: 002_add_gst_tables
Create Date: 2024-01-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_add_tds_tables'
down_revision = '002_add_gst_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tds_entries table
    op.create_table(
        'tds_entries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('transaction_id', sa.String(36), sa.ForeignKey('transactions.id'), nullable=True),
        sa.Column('vendor_pan', sa.String(10), nullable=True),
        sa.Column('vendor_name', sa.String(255), nullable=True),
        sa.Column('vendor_type', sa.String(20), default='unknown'),
        sa.Column('vendor_gstin', sa.String(15), nullable=True),
        sa.Column('payment_date', sa.DateTime(), nullable=False),
        sa.Column('payment_amount', sa.Float(), nullable=False, default=0),
        sa.Column('tds_section', sa.String(10), nullable=False),
        sa.Column('tds_rate', sa.Float(), nullable=False, default=0),
        sa.Column('tds_amount', sa.Float(), nullable=False, default=0),
        sa.Column('tds_deducted', sa.Float(), nullable=False, default=0),
        sa.Column('is_deducted', sa.Boolean(), default=False),
        sa.Column('missed_deduction', sa.Boolean(), default=False),
        sa.Column('is_pan_available', sa.Boolean(), default=True),
        sa.Column('penalty_estimate', sa.Float(), default=0),
        sa.Column('months_delayed', sa.Integer(), default=0),
        sa.Column('financial_year', sa.String(7), nullable=False),
        sa.Column('quarter', sa.String(2), nullable=False),
        sa.Column('source_category', sa.String(100), nullable=True),
        sa.Column('source_narration', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Indexes for tds_entries
    op.create_index('idx_tds_client_fy', 'tds_entries', ['client_id', 'financial_year'])
    op.create_index('idx_tds_client_quarter', 'tds_entries', ['client_id', 'financial_year', 'quarter'])
    op.create_index('idx_tds_vendor_fy', 'tds_entries', ['client_id', 'vendor_pan', 'financial_year'])
    op.create_index('idx_tds_missed', 'tds_entries', ['client_id', 'missed_deduction', 'is_deducted'])
    op.create_index('idx_tds_section', 'tds_entries', ['tds_section'])

    # Create tds_vendor_cumulative table
    op.create_table(
        'tds_vendor_cumulative',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('vendor_pan', sa.String(10), nullable=False),
        sa.Column('vendor_name', sa.String(255), nullable=True),
        sa.Column('vendor_type', sa.String(20), default='unknown'),
        sa.Column('tds_section', sa.String(10), nullable=False),
        sa.Column('financial_year', sa.String(7), nullable=False),
        sa.Column('total_payments', sa.Float(), default=0),
        sa.Column('total_tds_computed', sa.Float(), default=0),
        sa.Column('total_tds_deducted', sa.Float(), default=0),
        sa.Column('total_tds_missed', sa.Float(), default=0),
        sa.Column('threshold_single', sa.Float(), default=0),
        sa.Column('threshold_aggregate', sa.Float(), default=0),
        sa.Column('threshold_crossed', sa.Boolean(), default=False),
        sa.Column('threshold_crossed_date', sa.DateTime(), nullable=True),
        sa.Column('payment_count', sa.Integer(), default=0),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Indexes for tds_vendor_cumulative
    op.create_index('idx_tds_cum_vendor', 'tds_vendor_cumulative', 
                    ['client_id', 'vendor_pan', 'tds_section', 'financial_year'])
    op.create_index('idx_tds_cum_threshold', 'tds_vendor_cumulative', ['client_id', 'threshold_crossed'])

    # Create tds_return_batches table
    op.create_table(
        'tds_return_batches',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('financial_year', sa.String(7), nullable=False),
        sa.Column('quarter', sa.String(2), nullable=False),
        sa.Column('tan', sa.String(10), nullable=True),
        sa.Column('pan', sa.String(10), nullable=True),
        sa.Column('status', sa.String(20), default='draft'),
        sa.Column('filed_at', sa.DateTime(), nullable=True),
        sa.Column('filed_by', sa.String(100), nullable=True),
        sa.Column('total_entries', sa.Integer(), default=0),
        sa.Column('total_tds_amount', sa.Float(), default=0),
        sa.Column('xml_path', sa.String(500), nullable=True),
        sa.Column('fvu_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Index for tds_return_batches
    op.create_index('idx_tds_batch_period', 'tds_return_batches', 
                    ['client_id', 'financial_year', 'quarter'])


def downgrade() -> None:
    op.drop_index('idx_tds_batch_period', table_name='tds_return_batches')
    op.drop_table('tds_return_batches')

    op.drop_index('idx_tds_cum_threshold', table_name='tds_vendor_cumulative')
    op.drop_index('idx_tds_cum_vendor', table_name='tds_vendor_cumulative')
    op.drop_table('tds_vendor_cumulative')

    op.drop_index('idx_tds_section', table_name='tds_entries')
    op.drop_index('idx_tds_missed', table_name='tds_entries')
    op.drop_index('idx_tds_vendor_fy', table_name='tds_entries')
    op.drop_index('idx_tds_client_quarter', table_name='tds_entries')
    op.drop_index('idx_tds_client_fy', table_name='tds_entries')
    op.drop_table('tds_entries')
