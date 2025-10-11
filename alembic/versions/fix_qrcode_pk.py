"""
Alembic migration to fix dual primary key in qrcodes table.
Removes primary_key from qr_code_id, keeps only id as PK, makes qr_code_id unique and indexed.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fix_qrcode_pk'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Drop primary key constraint on qr_code_id if exists
    with op.batch_alter_table('qrcodes') as batch_op:
        batch_op.drop_constraint('qrcodes_pkey', type_='primary')
        batch_op.create_primary_key('pk_qrcodes', ['id'])
        batch_op.create_unique_constraint('uq_qrcode_id', ['qr_code_id'])
        batch_op.create_index('ix_qrcode_id', ['qr_code_id'])

def downgrade():
    # Revert to dual primary key (not recommended)
    with op.batch_alter_table('qrcodes') as batch_op:
        batch_op.drop_constraint('pk_qrcodes', type_='primary')
        batch_op.drop_constraint('uq_qrcode_id', type_='unique')
        batch_op.drop_index('ix_qrcode_id')
        batch_op.create_primary_key('qrcodes_pkey', ['id', 'qr_code_id'])
