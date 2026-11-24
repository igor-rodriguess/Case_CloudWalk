"""isolamento por marca com Row Level Security

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-24

As leituras feitas em nome de uma marca (painel e telas com `?marca=`) trocam, na própria
transação, para o papel `leitura_marca` e fixam `app.marca`. As políticas abaixo valem só para
esse papel: uma sessão da `jim` não lê linha da `infinitepay`, nem por engano na consulta. Os
processos do núcleo (que atendem as duas marcas) seguem com o papel da aplicação. Mensagens e
escalas não têm coluna de marca: herdam a política da conversa.
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

TABELAS = ("conversas", "clientes", "mensagens", "escalas", "eventos", "atendentes", "atribuicoes")


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leitura_marca') THEN
                CREATE ROLE leitura_marca NOLOGIN NOSUPERUSER NOBYPASSRLS;
            END IF;
        END $$;
        """
    )
    op.execute(f"GRANT SELECT ON {', '.join(TABELAS)}, versoes_regras TO leitura_marca")
    marca = "current_setting('app.marca', true)"
    op.execute(
        f"""
        ALTER TABLE conversas ENABLE ROW LEVEL SECURITY;
        ALTER TABLE clientes ENABLE ROW LEVEL SECURITY;
        ALTER TABLE mensagens ENABLE ROW LEVEL SECURITY;
        ALTER TABLE escalas ENABLE ROW LEVEL SECURITY;
        ALTER TABLE eventos ENABLE ROW LEVEL SECURITY;
        ALTER TABLE atendentes ENABLE ROW LEVEL SECURITY;
        ALTER TABLE atribuicoes ENABLE ROW LEVEL SECURITY;
        CREATE POLICY por_marca ON conversas FOR SELECT TO leitura_marca USING (marca = {marca});
        CREATE POLICY por_marca ON clientes FOR SELECT TO leitura_marca USING (marca = {marca});
        CREATE POLICY por_marca ON atendentes FOR SELECT TO leitura_marca USING (marca = {marca});
        CREATE POLICY por_marca ON mensagens FOR SELECT TO leitura_marca
            USING (EXISTS (SELECT 1 FROM conversas c WHERE c.id = mensagens.id_conversa));
        CREATE POLICY por_marca ON escalas FOR SELECT TO leitura_marca
            USING (EXISTS (SELECT 1 FROM conversas c WHERE c.id = escalas.id_conversa));
        CREATE POLICY por_marca ON eventos FOR SELECT TO leitura_marca
            USING (EXISTS (SELECT 1 FROM conversas c WHERE c.id = eventos.id_conversa));
        CREATE POLICY por_marca ON atribuicoes FOR SELECT TO leitura_marca
            USING (EXISTS (SELECT 1 FROM conversas c WHERE c.id = atribuicoes.id_conversa));
        """
    )


def downgrade() -> None:
    for t in TABELAS:
        op.execute(f"DROP POLICY IF EXISTS por_marca ON {t}; ALTER TABLE {t} DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE SELECT ON {', '.join(TABELAS)}, versoes_regras FROM leitura_marca")
    op.execute("DROP ROLE IF EXISTS leitura_marca")
