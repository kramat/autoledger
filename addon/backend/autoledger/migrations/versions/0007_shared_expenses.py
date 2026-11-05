"""shared expenses

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-05 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A batch copy of expenses is safe: no other table has a foreign key to it.
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.alter_column('vehicle_id', existing_type=sa.String(length=36), nullable=True)
        batch_op.add_column(sa.Column('split', sa.String(length=8), nullable=True))
        batch_op.add_column(sa.Column('split_vehicles', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    op.execute("DELETE FROM expenses WHERE vehicle_id IS NULL")
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_column('split_vehicles')
        batch_op.drop_column('split')
        batch_op.alter_column('vehicle_id', existing_type=sa.String(length=36), nullable=False)
