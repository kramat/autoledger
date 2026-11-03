"""attachments and depreciation

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-03 20:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

import autoledger.db


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('attachments',
    sa.Column('resource', sa.String(length=24), nullable=False),
    sa.Column('record_id', sa.String(length=36), nullable=False),
    sa.Column('filename', sa.String(length=200), nullable=False),
    sa.Column('mime_type', sa.String(length=80), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', autoledger.db.UTCDateTime(length=27), nullable=False),
    sa.Column('updated_at', autoledger.db.UTCDateTime(length=27), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('deleted_at', autoledger.db.UTCDateTime(length=27), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('attachments', schema=None) as batch_op:
        batch_op.create_index('ix_attachments_record', ['resource', 'record_id'], unique=False)

    # Plain ADD COLUMN: a batch copy of vehicles would have to drop a table other tables refer to.
    op.add_column('vehicles', sa.Column('resale_estimate', sa.Float(), nullable=True))
    op.add_column('vehicles', sa.Column('resale_date', sa.Date(), nullable=True))
    op.add_column('vehicles', sa.Column('depreciation_enabled', sa.Boolean(), nullable=False,
                                        server_default=sa.false()))


def downgrade() -> None:
    for column in ('depreciation_enabled', 'resale_date', 'resale_estimate'):
        op.execute(f'ALTER TABLE vehicles DROP COLUMN {column}')  # SQLite 3.35+

    with op.batch_alter_table('attachments', schema=None) as batch_op:
        batch_op.drop_index('ix_attachments_record')

    op.drop_table('attachments')
