"""Drop the response column. We're gonna push straight to Bas.

Revision ID: 04d56b17edad
Revises: 60a4bfee242f
Create Date: 2020-12-11 08:26:57.780808

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '04d56b17edad'
down_revision = '60a4bfee242f'
branch_labels = None
depends_on = None

# Note that Sqlite is silly and has limitations on dropping columns. :-(
# See https://blog.miguelgrinberg.com/post/fixing-alter-table-errors-with-flask-migrate-and-sqlite

def upgrade():
    with op.batch_alter_table('metasysCrawl', schema=None) as batch_op:
        batch_op.drop_column('response')
    # op.drop_column('metasysCrawl', 'response')

def downgrade():
   # op.add_column('metasysCrawl', sa.Column('response', sa.Text(), nullable=True))
    with op.batch_alter_table('metasysCrawl', schema=None) as batch_op:
        batch_op.add_column(sa.Column('response', sa.Text(), nullable=True))