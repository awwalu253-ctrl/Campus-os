"""phase 2.0: notifications foundation

Revision ID: c69a8adc5a2b
Revises: 22db60538e17
Create Date: 2026-10-07 13:27:27.102611

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c69a8adc5a2b'
down_revision = '22db60538e17'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notifications',
    sa.Column('recipient_id', sa.String(length=36), nullable=False),
    sa.Column('type', sa.String(length=48), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('body', sa.String(length=500), nullable=True),
    sa.Column('action_url', sa.String(length=255), nullable=True),
    sa.Column('campus_id', sa.String(length=36), nullable=True),
    sa.Column('related_entity_type', sa.String(length=32), nullable=True),
    sa.Column('related_entity_id', sa.String(length=36), nullable=True),
    sa.Column('dedupe_key', sa.String(length=255), nullable=True),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['campus_id'], ['campuses.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index('ix_notifications_campus_created', ['campus_id', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_campus_id'), ['campus_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_read_at'), ['read_at'], unique=False)
        batch_op.create_index('ix_notifications_recipient_created', ['recipient_id', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_recipient_id'), ['recipient_id'], unique=False)
        batch_op.create_index('ix_notifications_recipient_unread', ['recipient_id'], unique=False, postgresql_where=sa.text('read_at IS NULL AND dismissed_at IS NULL'))
        batch_op.create_index(batch_op.f('ix_notifications_related_entity_id'), ['related_entity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_type'), ['type'], unique=False)
        batch_op.create_index('uq_notifications_recipient_dedupe', ['recipient_id', 'dedupe_key'], unique=True, postgresql_where=sa.text('dedupe_key IS NOT NULL'))


def downgrade():
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index('uq_notifications_recipient_dedupe', postgresql_where=sa.text('dedupe_key IS NOT NULL'))
        batch_op.drop_index(batch_op.f('ix_notifications_type'))
        batch_op.drop_index(batch_op.f('ix_notifications_related_entity_id'))
        batch_op.drop_index('ix_notifications_recipient_unread', postgresql_where=sa.text('read_at IS NULL AND dismissed_at IS NULL'))
        batch_op.drop_index(batch_op.f('ix_notifications_recipient_id'))
        batch_op.drop_index('ix_notifications_recipient_created')
        batch_op.drop_index(batch_op.f('ix_notifications_read_at'))
        batch_op.drop_index(batch_op.f('ix_notifications_campus_id'))
        batch_op.drop_index('ix_notifications_campus_created')

    op.drop_table('notifications')