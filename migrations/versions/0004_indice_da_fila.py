"""índice parcial da fila do distribuidor

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-23

Nos testes de carga, a consulta que pega a próxima conversa varria a tabela `conversas` inteira
a cada conversa distribuída (25 ms com 3.271 na fila e 16 mil no total), e o custo crescia
com a fila. O índice parcial restringe a leitura às conversas que estão esperando.
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_conversas_fila_espera ON conversas (id_fila, prioridade) "
        "WHERE estado IN ('na_fila', 'escalada')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_conversas_fila_espera")
