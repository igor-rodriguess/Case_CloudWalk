"""tempo estimado na escala, SLA com pausa, retenção e expurgo, escala a pedido em qualquer turno

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-24

- `escalas.tempo_estimado_s`: o tempo de espera informado ao cliente quando ele pede um humano.
- SLA da conversa: relógio que corre enquanto a operação deve uma resposta e pausa enquanto o
  cliente deve uma (`sla_acumulado_ms` guarda o já corrido; `sla_desde` marca o trecho aberto).
- Retenção: `conversas.ouvidoria` preserva a conversa no expurgo; `mensagens.expurgada_em` marca
  o corpo apagado (a linha fica, para a contagem e a auditoria).
- Transição `na_fila -> escalada` pelo cliente: o pedido de atendente vale também antes de a IA
  pegar a conversa.
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE escalas ADD COLUMN tempo_estimado_s int;
        ALTER TABLE conversas ADD COLUMN sla_acumulado_ms bigint NOT NULL DEFAULT 0;
        ALTER TABLE conversas ADD COLUMN sla_desde timestamptz;
        ALTER TABLE conversas ADD COLUMN sla_limite_s int;
        ALTER TABLE conversas ADD COLUMN ouvidoria boolean NOT NULL DEFAULT false;
        ALTER TABLE mensagens ADD COLUMN expurgada_em timestamptz;
        INSERT INTO transicoes_permitidas VALUES ('na_fila', 'escalada', 'cliente') ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM transicoes_permitidas WHERE de = 'na_fila' AND para = 'escalada' AND ator_tipo = 'cliente';
        ALTER TABLE mensagens DROP COLUMN expurgada_em;
        ALTER TABLE conversas DROP COLUMN ouvidoria, DROP COLUMN sla_limite_s, DROP COLUMN sla_desde,
            DROP COLUMN sla_acumulado_ms;
        ALTER TABLE escalas DROP COLUMN tempo_estimado_s;
        """
    )
