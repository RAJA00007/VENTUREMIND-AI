"""canonical schema repair

Revision ID: b2b07e15d89f
Revises: a832bc9d7110
Create Date: 2026-09-13 20:30:00.000000

"""
from typing import Sequence, Union
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b2b07e15d89f'
down_revision: Union[str, Sequence[str], None] = 'a832bc9d7110'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    # JSON type with Postgres JSONB variant
    json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")

    # 1. Reconcile / Create companies table
    if not insp.has_table('companies'):
        op.create_table(
            'companies',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('cin', sa.String(length=21), nullable=True),
            sa.Column('company_name', sa.String(length=255), nullable=False),
            sa.Column('legal_name', sa.String(length=255), nullable=False),
            sa.Column('incorporation_date', sa.Date(), nullable=True),
            sa.Column('company_status', sa.String(length=50), nullable=False, server_default='Active'),
            sa.Column('company_type', sa.String(length=50), nullable=True),
            sa.Column('registered_state', sa.String(length=100), nullable=True),
            sa.Column('roc', sa.String(length=100), nullable=True),
            sa.Column('dpiit_recognized', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('dpiit_certificate_number', sa.String(length=100), nullable=True),
            sa.Column('industry', sa.String(length=100), nullable=True),
            sa.Column('sub_industry', sa.String(length=100), nullable=True),
            sa.Column('website', sa.String(length=255), nullable=True),
            sa.Column('source', sa.String(length=100), nullable=False, server_default='MCA Ingestion'),
            sa.Column('source_url', sa.String(length=500), nullable=True),
            sa.Column('confidence_score', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('last_verified_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )
        op.create_index(op.f('ix_companies_id'), 'companies', ['id'], unique=False)
        op.create_index(op.f('ix_companies_cin'), 'companies', ['cin'], unique=True)
        op.create_index(op.f('ix_companies_company_name'), 'companies', ['company_name'], unique=False)
        op.create_index(op.f('ix_companies_industry'), 'companies', ['industry'], unique=False)
        op.create_index(op.f('ix_companies_dpiit_recognized'), 'companies', ['dpiit_recognized'], unique=False)
        op.create_index(op.f('ix_companies_created_by_user_id'), 'companies', ['created_by_user_id'], unique=False)
    else:
        # Check if table has old prototype schema ('name' instead of 'company_name')
        company_cols = [c['name'] for c in insp.get_columns('companies')]
        if 'name' in company_cols and 'company_name' not in company_cols:
            # Upgrade prototype companies table safely
            # If empty (as in fresh DB), drop prototype and recreate canonical
            row_count = bind.execute(sa.text("SELECT count(*) FROM companies")).scalar()
            if row_count == 0:
                op.drop_table('companies')
                op.create_table(
                    'companies',
                    sa.Column('id', sa.String(length=36), primary_key=True),
                    sa.Column('cin', sa.String(length=21), nullable=True),
                    sa.Column('company_name', sa.String(length=255), nullable=False),
                    sa.Column('legal_name', sa.String(length=255), nullable=False),
                    sa.Column('incorporation_date', sa.Date(), nullable=True),
                    sa.Column('company_status', sa.String(length=50), nullable=False, server_default='Active'),
                    sa.Column('company_type', sa.String(length=50), nullable=True),
                    sa.Column('registered_state', sa.String(length=100), nullable=True),
                    sa.Column('roc', sa.String(length=100), nullable=True),
                    sa.Column('dpiit_recognized', sa.Boolean(), nullable=False, server_default=sa.false()),
                    sa.Column('dpiit_certificate_number', sa.String(length=100), nullable=True),
                    sa.Column('industry', sa.String(length=100), nullable=True),
                    sa.Column('sub_industry', sa.String(length=100), nullable=True),
                    sa.Column('website', sa.String(length=255), nullable=True),
                    sa.Column('source', sa.String(length=100), nullable=False, server_default='MCA Ingestion'),
                    sa.Column('source_url', sa.String(length=500), nullable=True),
                    sa.Column('confidence_score', sa.Float(), nullable=False, server_default='1.0'),
                    sa.Column('last_verified_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
                    sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
                    sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
                    sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
                )
                op.create_index(op.f('ix_companies_id'), 'companies', ['id'], unique=False)
                op.create_index(op.f('ix_companies_cin'), 'companies', ['cin'], unique=True)
                op.create_index(op.f('ix_companies_company_name'), 'companies', ['company_name'], unique=False)
                op.create_index(op.f('ix_companies_industry'), 'companies', ['industry'], unique=False)
                op.create_index(op.f('ix_companies_dpiit_recognized'), 'companies', ['dpiit_recognized'], unique=False)
                op.create_index(op.f('ix_companies_created_by_user_id'), 'companies', ['created_by_user_id'], unique=False)
        else:
            # Canonical columns already present, ensure created_by_user_id exists
            if 'created_by_user_id' not in company_cols:
                with op.batch_alter_table('companies') as batch_op:
                    batch_op.add_column(sa.Column('created_by_user_id', sa.Integer(), nullable=True))
                    batch_op.create_foreign_key('fk_companies_created_by_user_id', 'users', ['created_by_user_id'], ['id'], ondelete='SET NULL')
                    batch_op.create_index(op.f('ix_companies_created_by_user_id'), ['created_by_user_id'], unique=False)

    # 2. Child tables for companies
    if not insp.has_table('founders'):
        op.create_table(
            'founders',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('company_id', sa.String(length=36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('din', sa.String(length=8), nullable=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('title', sa.String(length=100), nullable=False, server_default='Co-Founder'),
            sa.Column('linkedin_url', sa.String(length=255), nullable=True),
            sa.Column('github_handle', sa.String(length=100), nullable=True),
            sa.Column('prior_exits', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(op.f('ix_founders_company_id'), 'founders', ['company_id'], unique=False)
        op.create_index(op.f('ix_founders_name'), 'founders', ['name'], unique=False)

    if not insp.has_table('funding_rounds'):
        op.create_table(
            'funding_rounds',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('company_id', sa.String(length=36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('round_type', sa.String(length=50), nullable=False),
            sa.Column('amount_usd', sa.Numeric(precision=15, scale=2), nullable=True),
            sa.Column('valuation_usd', sa.Numeric(precision=15, scale=2), nullable=True),
            sa.Column('announced_date', sa.Date(), nullable=True),
            sa.Column('source', sa.String(length=100), nullable=True),
            sa.Column('source_url', sa.String(length=500), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(op.f('ix_funding_rounds_company_id'), 'funding_rounds', ['company_id'], unique=False)

    if not insp.has_table('company_financials'):
        op.create_table(
            'company_financials',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('company_id', sa.String(length=36), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('fiscal_year', sa.String(length=10), nullable=False),
            sa.Column('revenue_inr', sa.Numeric(precision=15, scale=2), nullable=True),
            sa.Column('ebitda_inr', sa.Numeric(precision=15, scale=2), nullable=True),
            sa.Column('pat_inr', sa.Numeric(precision=15, scale=2), nullable=True),
            sa.Column('burn_rate_monthly', sa.Numeric(precision=15, scale=2), nullable=True),
            sa.Column('runway_months', sa.Integer(), nullable=True),
            sa.Column('source', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(op.f('ix_company_financials_company_id'), 'company_financials', ['company_id'], unique=False)

    # 3. Upgrade analyses table (user_id NOT NULL, company_id nullable FK)
    if insp.has_table('analyses'):
        analysis_cols = [c['name'] for c in insp.get_columns('analyses')]
        with op.batch_alter_table('analyses') as batch_op:
            if 'user_id' not in analysis_cols:
                batch_op.add_column(
                    sa.Column('user_id', sa.Integer(), nullable=False, server_default='1')
                )
                batch_op.create_foreign_key('fk_analyses_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE')
                batch_op.create_index(op.f('ix_analyses_user_id'), ['user_id'], unique=False)
            if 'company_id' not in analysis_cols:
                batch_op.add_column(
                    sa.Column('company_id', sa.String(length=36), nullable=True)
                )
                batch_op.create_foreign_key('fk_analyses_company_id', 'companies', ['company_id'], ['id'], ondelete='SET NULL')
                batch_op.create_index(op.f('ix_analyses_company_id'), ['company_id'], unique=False)

        existing_indices = [idx['name'] for idx in insp.get_indexes('analyses')]
        if 'ix_analyses_company_name' not in existing_indices:
            op.create_index(op.f('ix_analyses_company_name'), 'analyses', ['company_name'], unique=False)
        if 'ix_analyses_created_at' not in existing_indices:
            op.create_index(op.f('ix_analyses_created_at'), 'analyses', ['created_at'], unique=False)


    # 4. Analysis jobs indexing & composite index for deduplication acceleration
    if insp.has_table('analysis_jobs'):
        job_indices = [idx['name'] for idx in insp.get_indexes('analysis_jobs')]
        if 'ix_analysis_jobs_created_at' not in job_indices:
            op.create_index(op.f('ix_analysis_jobs_created_at'), 'analysis_jobs', ['created_at'], unique=False)
        if 'ix_analysis_jobs_user_status_company' not in job_indices:
            op.create_index('ix_analysis_jobs_user_status_company', 'analysis_jobs', ['user_id', 'status', 'company_name'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table('company_financials'):
        op.drop_table('company_financials')
    if insp.has_table('funding_rounds'):
        op.drop_table('funding_rounds')
    if insp.has_table('founders'):
        op.drop_table('founders')

    if insp.has_table('analyses'):
        with op.batch_alter_table('analyses') as batch_op:
            batch_op.drop_index(op.f('ix_analyses_created_at'))
            batch_op.drop_index(op.f('ix_analyses_company_name'))
            batch_op.drop_index(op.f('ix_analyses_company_id'))
            batch_op.drop_index(op.f('ix_analyses_user_id'))
            batch_op.drop_column('company_id')
            batch_op.drop_column('user_id')
