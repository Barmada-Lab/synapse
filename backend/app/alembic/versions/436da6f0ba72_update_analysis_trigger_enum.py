"""update analysis trigger enum

Revision ID: 436da6f0ba72
Revises: 63b126facc06
Create Date: 2025-01-07 11:15:38.212121

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '436da6f0ba72'
down_revision = '63b126facc06'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE analysistrigger RENAME VALUE 'POST_ACQUISTION' TO 'END_OF_RUN';")

    op.execute("ALTER TYPE artifacttype RENAME VALUE 'ACQUISITION' TO 'ACQUISITION_DATA';")
    op.execute("ALTER TYPE artifacttype RENAME VALUE 'ANALYSIS' TO 'ANALYSIS_DATA';")

    op.execute("ALTER TYPE repository RENAME VALUE 'ACQUISITION' TO 'ACQUISITION_STORE';")
    op.execute("ALTER TYPE repository RENAME VALUE 'ANALYSIS' TO 'ANALYSIS_STORE';")
    op.execute("ALTER TYPE repository RENAME VALUE 'ARCHIVE' TO 'ARCHIVE_STORE';")


def downgrade():
    op.execute("ALTER TYPE analysistrigger RENAME VALUE 'END_OF_RUN' TO 'POST_ACQUISTION';")

    op.execute("ALTER TYPE artifacttype RENAME VALUE 'ACQUISITION_DATA' TO 'ACQUISITION';")
    op.execute("ALTER TYPE artifacttype RENAME VALUE 'ANALYSIS_DATA' TO 'ANALYSIS';")

    op.execute("ALTER TYPE repository RENAME VALUE 'ACQUISITION_STORE' TO 'ACQUISITION';")
    op.execute("ALTER TYPE repository RENAME VALUE 'ANALYSIS_STORE' TO 'ANALYSIS';")
    op.execute("ALTER TYPE repository RENAME VALUE 'ARCHIVE_STORE' TO 'ARCHIVE';")
