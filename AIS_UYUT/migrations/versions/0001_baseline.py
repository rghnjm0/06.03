"""Baseline marker for databases initialized by the original application.

Revision ID: 0001_baseline
Revises: None
"""
revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Baseline only: legacy tables are created by db.py on fresh installations.
    # New schema changes must be added as forward Alembic revisions.
    pass


def downgrade():
    # Intentionally non-destructive; never drop production hotel data here.
    pass
