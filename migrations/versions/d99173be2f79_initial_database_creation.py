"""Initial database creation

Revision ID: d99173be2f79
Revises: 
Create Date: 2020-10-21 12:11:58.788882

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd99173be2f79'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('metasysCrawl',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('parentId', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('type', sa.Integer(), nullable=False),
    sa.Column('discovered', sa.DateTime(), nullable=False),
    sa.Column('lastCrawl', sa.DateTime(), nullable=True),
    sa.Column('lastError', sa.DateTime(), nullable=True),
    sa.Column('successes', sa.Integer(), nullable=False),
    sa.Column('errors', sa.Integer(), nullable=False),
    sa.Column('response', sa.Text(), nullable=True),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('itemReference', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_metasysCrawl_parentId'), 'metasysCrawl', ['parentId'], unique=False)
    op.create_index(op.f('ix_metasysCrawl_type'), 'metasysCrawl', ['type'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_metasysCrawl_type'), table_name='metasysCrawl')
    op.drop_index(op.f('ix_metasysCrawl_parentId'), table_name='metasysCrawl')
    op.drop_table('metasysCrawl')
    # ### end Alembic commands ###
