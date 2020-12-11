"""Remove network devices

Revision ID: 60a4bfee242f
Revises: dfa4b3c04a8c
Create Date: 2020-12-10 11:57:43.374537

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '60a4bfee242f'
down_revision = 'dfa4b3c04a8c'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index(op.f('ix_metasysCrawlNetworkDevice_parentId'), table_name='metasysCrawlNetworkDevice')
    op.drop_table('metasysCrawlNetworkDevice')

def downgrade():
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

