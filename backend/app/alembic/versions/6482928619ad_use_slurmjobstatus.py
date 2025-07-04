"""Use SlurmJobStatus with SBatchAnalysisSpec

also rename analysis_status to status

Revision ID: 6482928619ad
Revises: d8b2902c8d27
Create Date: 2024-11-27 14:13:08.283833

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '6482928619ad'
down_revision = 'd8b2902c8d27'
branch_labels = None
depends_on = None

SLURM_JOB_STATUS_ENUM = sa.Enum('UNSUBMITTED', 'COMPLETED', 'COMPLETING', 'PENDING', 'CANCELLED', 'FAILED', 'RUNNING', 'UNHANDLED', name='slurmjobstatus')
PROCESS_STATUS_ENUM = sa.Enum('PENDING', 'SCHEDULED', 'RUNNING', 'COMPLETED', 'CANCELLED', 'ABORTED', 'RESET', name='processstatus')

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    SLURM_JOB_STATUS_ENUM.create(op.get_bind())
    op.add_column('sbatchanalysisspec', sa.Column('status', SLURM_JOB_STATUS_ENUM, nullable=False))
    op.drop_column('sbatchanalysisspec', 'analysis_status')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('sbatchanalysisspec', sa.Column('analysis_status', PROCESS_STATUS_ENUM, nullable=False))
    op.drop_column('sbatchanalysisspec', 'status')
    SLURM_JOB_STATUS_ENUM.drop(op.get_bind())
    # ### end Alembic commands ###
