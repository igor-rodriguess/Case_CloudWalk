"""índice por horário em mensagens e escalas, para a série do painel ao vivo

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-25
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX ix_mensagens_criada_em ON mensagens (criada_em)")
    op.execute("CREATE INDEX ix_escalas_criada_em ON escalas (criada_em)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_mensagens_criada_em, ix_escalas_criada_em")
