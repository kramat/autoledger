"""vehicles with collector data are collector-tracked

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-04 12:00:00.000000
"""

from alembic import op


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Until 1.0.0 nothing set `tracking`, so every vehicle stayed "manual".
    op.execute(
        "UPDATE vehicles SET tracking = 'collector' WHERE id IN "
        "(SELECT DISTINCT vehicle_id FROM ingest_events WHERE result = 'applied' AND vehicle_id IS NOT NULL)"
    )


def downgrade() -> None:
    pass
