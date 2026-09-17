"""create analysis_jobs table

Revision ID: a832bc9d7110
Revises: f162e9ca2271
Create Date: 2026-09-13 19:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a832bc9d7110'
down_revision: Union[str, Sequence[str], None] = '0f4b3e8c1a2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table('analysis_jobs'):
        op.create_table(
            'analysis_jobs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('job_id', sa.String(length=64), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('company_name', sa.String(length=150), nullable=False),
            sa.Column('company_id', sa.String(length=150), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='queued'),
            sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('current_stage', sa.String(length=150), nullable=True),
            sa.Column('current_agent', sa.String(length=150), nullable=True),
            sa.Column('input_payload', sa.JSON(), nullable=False),
            sa.Column('analysis_id', sa.Integer(), nullable=True),
            sa.Column('error_message', sa.String(length=1000), nullable=True),
            sa.Column('error_type', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['analysis_id'], ['analyses.id'], ondelete='SET NULL')
        )
        op.create_index(op.f('ix_analysis_jobs_job_id'), 'analysis_jobs', ['job_id'], unique=True)
        op.create_index(op.f('ix_analysis_jobs_company_name'), 'analysis_jobs', ['company_name'], unique=False)
        op.create_index(op.f('ix_analysis_jobs_status'), 'analysis_jobs', ['status'], unique=False)
        op.create_index(op.f('ix_analysis_jobs_user_id'), 'analysis_jobs', ['user_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table('analysis_jobs'):
        op.drop_index(op.f('ix_analysis_jobs_user_id'), table_name='analysis_jobs')
        op.drop_index(op.f('ix_analysis_jobs_status'), table_name='analysis_jobs')
        op.drop_index(op.f('ix_analysis_jobs_company_name'), table_name='analysis_jobs')
        op.drop_index(op.f('ix_analysis_jobs_job_id'), table_name='analysis_jobs')
        op.drop_table('analysis_jobs')

