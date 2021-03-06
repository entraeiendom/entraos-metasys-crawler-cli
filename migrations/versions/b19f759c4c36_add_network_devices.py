"""Add network devices

Revision ID: b19f759c4c36
Revises: d99173be2f79
Create Date: 2020-10-21 12:21:20.315832

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b19f759c4c36'
down_revision = 'd99173be2f79'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('metasysCrawlNetworkDevice',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('parentId', sa.String(), nullable=True),
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
    op.create_index(op.f('ix_metasysCrawlNetworkDevice_parentId'), 'metasysCrawlNetworkDevice', ['parentId'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_metasysCrawlNetworkDevice_parentId'), table_name='metasysCrawlNetworkDevice')
    op.drop_table('metasysCrawlNetworkDevice')
    # ### end Alembic commands ###
