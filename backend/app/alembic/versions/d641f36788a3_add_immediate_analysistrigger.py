"""add IMMEDIATE AnalysisTrigger

Revision ID: d641f36788a3
Revises: 436da6f0ba72
Create Date: 2025-01-10 11:24:31.991079

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'd641f36788a3'
down_revision = '436da6f0ba72'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE analysistrigger ADD VALUE 'IMMEDIATE';")


def downgrade():
    pass
