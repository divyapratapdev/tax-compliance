"""
Add GST reconciliation tables.

Revision ID: 002_add_gst_tables
Revises: 001_add_needs_review
Create Date: 2024-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_add_gst_tables'
down_revision = '001_add_needs_review'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create gst_invoices table
    op.create_table(
        'gst_invoices',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('source', sa.String(20), default='uploaded'),
        sa.Column('supplier_gstin', sa.String(15), nullable=False),
        sa.Column('supplier_name', sa.String(255), nullable=True),
        sa.Column('invoice_number', sa.String(100), nullable=False),
        sa.Column('invoice_date', sa.DateTime(), nullable=True),
        sa.Column('taxable_amount', sa.Float(), default=0),
        sa.Column('cgst', sa.Float(), default=0),
        sa.Column('sgst', sa.Float(), default=0),
        sa.Column('igst', sa.Float(), default=0),
        sa.Column('cess', sa.Float(), default=0),
        sa.Column('total_amount', sa.Float(), default=0),
        sa.Column('total_tax', sa.Float(), default=0),
        sa.Column('period_month', sa.Integer(), nullable=False),
        sa.Column('period_year', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id'), nullable=True),
        sa.Column('reconciliation_status', sa.String(50), default='pending'),
        sa.Column('matched_with_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create indexes for gst_invoices
    op.create_index('idx_gst_inv_lookup', 'gst_invoices', 
                    ['client_id', 'supplier_gstin', 'invoice_number', 'period_month', 'period_year'])
    op.create_index('idx_gst_inv_period', 'gst_invoices', ['client_id', 'period_month', 'period_year'])
    op.create_index('idx_gst_inv_source', 'gst_invoices', ['client_id', 'source'])

    # Create reconciliation_runs table
    op.create_table(
        'reconciliation_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('period_month', sa.Integer(), nullable=False),
        sa.Column('period_year', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), default='running'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('total_invoices', sa.Integer(), default=0),
        sa.Column('matched_count', sa.Integer(), default=0),
        sa.Column('amount_mismatch_count', sa.Integer(), default=0),
        sa.Column('missing_in_2a_count', sa.Integer(), default=0),
        sa.Column('missing_in_books_count', sa.Integer(), default=0),
        sa.Column('gstin_mismatch_count', sa.Integer(), default=0),
        sa.Column('itc_safe_amount', sa.Float(), default=0),
        sa.Column('itc_at_risk_amount', sa.Float(), default=0),
        sa.Column('itc_missing_amount', sa.Float(), default=0),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )

    # Create index for reconciliation_runs
    op.create_index('idx_recon_run_period', 'reconciliation_runs', 
                    ['client_id', 'period_month', 'period_year'])
    op.create_index('idx_recon_run_status', 'reconciliation_runs', ['status'])

    # Create reconciliation_mismatches table
    op.create_table(
        'reconciliation_mismatches',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('reconciliation_runs.id'), nullable=False),
        sa.Column('mismatch_type', sa.String(50), nullable=False),
        sa.Column('client_invoice_id', sa.String(36), sa.ForeignKey('gst_invoices.id'), nullable=True),
        sa.Column('gstr2a_invoice_id', sa.String(36), sa.ForeignKey('gst_invoices.id'), nullable=True),
        sa.Column('supplier_gstin', sa.String(15), nullable=True),
        sa.Column('invoice_number', sa.String(100), nullable=True),
        sa.Column('client_amount', sa.Float(), nullable=True),
        sa.Column('gstr2a_amount', sa.Float(), nullable=True),
        sa.Column('difference_amount', sa.Float(), nullable=True),
        sa.Column('suggested_action', sa.Text(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), default=False),
        sa.Column('resolved_by', sa.String(100), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Create indexes for reconciliation_mismatches
    op.create_index('idx_mismatch_run', 'reconciliation_mismatches', ['run_id', 'mismatch_type'])
    op.create_index('idx_mismatch_unresolved', 'reconciliation_mismatches', ['run_id', 'is_resolved'])
    op.create_index('idx_mismatch_gstin', 'reconciliation_mismatches', ['supplier_gstin'])


def downgrade() -> None:
    # Drop in reverse order
    op.drop_index('idx_mismatch_gstin', table_name='reconciliation_mismatches')
    op.drop_index('idx_mismatch_unresolved', table_name='reconciliation_mismatches')
    op.drop_index('idx_mismatch_run', table_name='reconciliation_mismatches')
    op.drop_table('reconciliation_mismatches')

    op.drop_index('idx_recon_run_status', table_name='reconciliation_runs')
    op.drop_index('idx_recon_run_period', table_name='reconciliation_runs')
    op.drop_table('reconciliation_runs')

    op.drop_index('idx_gst_inv_source', table_name='gst_invoices')
    op.drop_index('idx_gst_inv_period', table_name='gst_invoices')
    op.drop_index('idx_gst_inv_lookup', table_name='gst_invoices')
    op.drop_table('gst_invoices')
