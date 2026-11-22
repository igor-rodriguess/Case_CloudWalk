"""índices que o primeiro lote do experimento mostrou faltar

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-22

Sob carga, outbox, conversas e agendamentos eram varridas por inteiro a cada consulta
(pg_stat_user_tables: 84 mil, 52 mil e 24 mil varreduras sequenciais).
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX ix_outbox_pendentes ON outbox (criado_em)
            WHERE status IN ('pendente', 'enviando');
        CREATE INDEX ix_conversas_cliente ON conversas (id_cliente, marca);
        CREATE INDEX ix_agendamentos_referencia ON agendamentos (referencia)
            WHERE tipo = 'timeout_agente';
        ANALYZE outbox; ANALYZE conversas; ANALYZE agendamentos;
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_outbox_pendentes, ix_conversas_cliente, ix_agendamentos_referencia"
    )
