"""Testes de integração da seção 13.1 do guia, contra um Postgres real.

Usam um banco descartável (`helpdesk_teste_<aleatório>`) no Postgres do compose (porta 5433),
criado e migrado aqui e apagado no fim. Não tocam no banco da demonstração.
Uso: .venv\\Scripts\\python -m pytest testes/test_integracao.py
"""

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest

if sys.platform == "win32":  # psycopg assíncrono não roda no ProactorEventLoop do Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

RAIZ = Path(__file__).resolve().parent.parent
BASE = os.getenv("TESTE_PG", "postgresql://helpdesk:helpdesk@localhost:5433")
NOME = f"helpdesk_teste_{uuid.uuid4().hex[:8]}"
# Se outro arquivo de teste já importou o núcleo, a configuração aponta para o banco da demo:
# nesse caso este arquivo não roda (proteção contra apagar ou sujar dados reais da demo).
_JA_IMPORTADO = "nucleo.config" in sys.modules
os.environ["DATABASE_URL"] = f"postgresql+psycopg://{BASE.split('://', 1)[1]}/{NOME}"
os.environ["WORKERS_ATIVOS"] = "false"


def _pg_disponivel() -> bool:
    try:
        psycopg.connect(f"{BASE}/postgres", connect_timeout=3).close()
        return True
    except psycopg.Error:
        return False


pytestmark = [
    pytest.mark.skipif(_JA_IMPORTADO, reason="rode sozinho: pytest testes/test_integracao.py"),
    pytest.mark.skipif(not _pg_disponivel(), reason="Postgres do compose não está no ar"),
]


@pytest.fixture(scope="module", autouse=True)
def banco():
    with psycopg.connect(f"{BASE}/postgres", autocommit=True) as c:
        c.execute(f"CREATE DATABASE {NOME}")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=RAIZ, check=True,
                   env={**os.environ}, capture_output=True)
    from nucleo.infra.seed import semear

    rodar(semear())
    yield
    from nucleo.infra.banco import engine

    asyncio.run(engine.dispose())
    with psycopg.connect(f"{BASE}/postgres", autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {NOME} WITH (FORCE)")


def rodar(coro):
    """Cada teste roda num laço próprio; o pool é descartado no fim para não cruzar laços."""
    from nucleo.infra.banco import engine

    async def com_descarte():
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(com_descarte())


def sql(consulta: str, *params):
    with psycopg.connect(f"{BASE}/{NOME}", autocommit=True) as c:
        cur = c.execute(consulta, params)
        return cur.fetchall() if cur.description else None


def nova_conversa(estado: str = "na_fila") -> uuid.UUID:
    cli, conv = uuid.uuid4(), uuid.uuid4()
    sql("INSERT INTO clientes (id, marca, nome) VALUES (%s, 'infinitepay', 'teste')", cli)
    sql("INSERT INTO conversas (id, id_cliente, marca, canal, estado, id_fila) "
        "VALUES (%s, %s, 'infinitepay', 'chat', %s, 'infinitepay-geral')", conv, cli, estado)
    return conv


def analista(capacidade: int = 3) -> uuid.UUID:
    a = uuid.uuid4()
    sql("INSERT INTO atendentes (id, tipo, nome, marca, id_equipe, capacidade) "
        "VALUES (%s, 'humano', 'Teste', 'infinitepay', 'suporte-br', %s)", a, capacidade)
    return a


async def _transicionar(id_conversa, para, ator_tipo="sistema", **kw):
    from nucleo.dominio.transicionar import Ator, transicionar
    from nucleo.infra.banco import unidade

    async with unidade() as s:
        resultado, _ = await transicionar(s, id_conversa, para, Ator(ator_tipo), **kw)
    return resultado


def test_transicionar_concorrente_uma_aplica_a_outra_ve_o_estado_novo():
    from nucleo.dominio.transicionar import Resultado

    conv, a = nova_conversa(), analista()

    async def duas():
        return await asyncio.gather(_transicionar(conv, "com_humano", id_atendente=a),
                                    _transicionar(conv, "com_humano", id_atendente=a))

    resultados = rodar(duas())
    assert sorted(r.value for r in resultados) == sorted([Resultado.APLICADO.value, Resultado.REJEITADO.value])
    assert sql("SELECT count(*) FROM atribuicoes WHERE id_conversa = %s", conv)[0][0] == 1


def test_transicao_fora_da_tabela_e_rejeitada_e_auditada():
    from nucleo.dominio.transicionar import Resultado

    conv = nova_conversa("na_fila")
    assert rodar(_transicionar(conv, "resolvida", "ia")) == Resultado.REJEITADO
    assert sql("SELECT count(*) FROM eventos WHERE id_conversa = %s AND tipo = 'transicao_invalida'", conv)[0][0] == 1


def test_fencing_descarta_evento_de_atribuicao_vencida():
    from nucleo.dominio.transicionar import Resultado

    conv, a = nova_conversa(), analista()
    assert rodar(_transicionar(conv, "com_humano", id_atendente=a)) == Resultado.APLICADO
    vencida = uuid.uuid4()
    mensagem = {"autor_tipo": "ia", "conteudo": "atrasada"}
    assert rodar(_transicionar(conv, None, "ia", id_atribuicao=vencida, mensagem=mensagem)) == Resultado.DESCARTADO
    assert sql("SELECT count(*) FROM mensagens WHERE id_conversa = %s", conv)[0][0] == 0
    assert sql("SELECT count(*) FROM eventos WHERE id_conversa = %s AND tipo = 'evento_descartado'", conv)[0][0] == 1


def test_capacidade_sob_concorrencia():
    from nucleo.dominio.transicionar import Resultado

    a = analista(capacidade=1)
    c1, c2 = nova_conversa(), nova_conversa()

    async def duas():
        return await asyncio.gather(_transicionar(c1, "com_humano", id_atendente=a),
                                    _transicionar(c2, "com_humano", id_atendente=a))

    resultados = sorted(r.value for r in rodar(duas()))
    assert resultados == sorted([Resultado.APLICADO.value, Resultado.SEM_CAPACIDADE.value])
    assert sql("SELECT ativas FROM atendentes WHERE id = %s", a)[0][0] == 1


def test_sem_capacidade_nao_deixa_a_conversa_sem_dono():
    from nucleo.dominio.transicionar import Resultado

    dono, cheio = analista(), analista(capacidade=0)
    conv = nova_conversa()
    assert rodar(_transicionar(conv, "com_humano", id_atendente=dono)) == Resultado.APLICADO
    # com_humano -> com_ia exige ator humano; usa um atendente sem capacidade como destino
    assert rodar(_transicionar(conv, "com_ia", "humano", id_atendente=cheio)) == Resultado.SEM_CAPACIDADE
    estado, atendente = sql("SELECT estado, id_atendente FROM conversas WHERE id = %s", conv)[0]
    assert estado == "com_humano" and atendente == dono


def test_eventos_sao_so_insercao():
    with pytest.raises(psycopg.errors.RaiseException):
        sql("UPDATE eventos SET tipo = 'x' WHERE id = (SELECT min(id) FROM eventos)")


def test_uma_conversa_aberta_por_cliente_e_marca():
    conv = nova_conversa()
    cli = sql("SELECT id_cliente FROM conversas WHERE id = %s", conv)[0][0]
    with pytest.raises(psycopg.errors.UniqueViolation):
        sql("INSERT INTO conversas (id, id_cliente, marca, canal, estado) VALUES (%s, %s, 'infinitepay', 'chat', 'nova')",
            uuid.uuid4(), cli)


def test_api_deduplica_reenvio_do_canal_e_evento_do_agente():
    from fastapi.testclient import TestClient

    from nucleo.main import app

    with TestClient(app) as cliente:
        corpo = {"canal": "chat", "marca": "infinitepay", "identificador": f"t-{uuid.uuid4().hex[:6]}",
                 "conteudo": "meu repasse não caiu", "id_externo": f"x-{uuid.uuid4().hex[:6]}"}
        primeira = cliente.post("/mensagens", json=corpo).json()
        segunda = cliente.post("/mensagens", json=corpo).json()
        assert primeira["duplicada"] is False and segunda["duplicada"] is True
        conv = primeira["id_conversa"]
        assert sql("SELECT count(*) FROM mensagens WHERE id_conversa = %s", conv)[0][0] == 1

        a = analista()
        sql("UPDATE conversas SET estado = 'com_ia' WHERE id = %s", conv)
        atr = uuid.uuid4()
        sql("INSERT INTO atribuicoes (id, id_conversa, id_atendente) VALUES (%s, %s, %s)", atr, conv, a)
        sql("UPDATE conversas SET id_atribuicao_atual = %s WHERE id = %s", atr, conv)
        evento = {"versao": "1.0", "id_evento": str(uuid.uuid4()), "tipo": "mensagem.enviada",
                  "id_conversa": conv, "id_atribuicao": str(atr), "causado_por": str(uuid.uuid4()),
                  "marca": "infinitepay", "timestamp": "2026-11-22T10:00:00-03:00",
                  "dados": {"conteudo": "Vou verificar.", "sequencia": 0}}
        r1 = cliente.post("/agente/eventos", json=evento)
        r2 = cliente.post("/agente/eventos", json=evento)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r2.json()["resultado"] == "duplicado"
        assert sql("SELECT count(*) FROM mensagens WHERE id_conversa = %s AND autor_tipo = 'ia'", conv)[0][0] == 1


def test_evento_de_tipo_desconhecido_e_auditado_e_confirmado():
    from fastapi.testclient import TestClient

    from nucleo.main import app

    with TestClient(app) as cliente:
        r = cliente.post("/agente/eventos", json={
            "versao": "1.4", "id_evento": str(uuid.uuid4()), "tipo": "agente.novidade", "id_conversa": str(uuid.uuid4()),
            "marca": "jim", "timestamp": "2026-11-22T10:00:00Z", "dados": {}})
        assert r.status_code == 200 and r.json()["resultado"] == "tipo_desconhecido"


def test_fila_da_equipe_filtra_antes_do_limite():
    """Com 210 escalas de outra equipe na frente, a da equipe ainda aparece (o LIMIT é 200)."""
    from fastapi.testclient import TestClient

    from nucleo.main import app

    def escala(fila: str, prioridade: int) -> uuid.UUID:
        conv = nova_conversa("escalada")
        sql("UPDATE conversas SET id_fila = %s, prioridade = %s WHERE id = %s", fila, prioridade, conv)
        return conv

    for _ in range(210):
        escala("escalas-jim", 3)
    da_equipe = escala("infinitepay-fraude", 1)
    with TestClient(app) as cliente:
        br = {x["id"] for x in cliente.get("/painel/fila", params={"equipe": "suporte-br"}).json()}
        us = cliente.get("/painel/fila", params={"equipe": "support-us"}).json()
        ninguem = cliente.get("/painel/fila", params={"equipe": "nao-existe"}).json()
    assert str(da_equipe) in br
    assert us and all(x["id_fila"] in ("escalas-jim", "jim-geral") for x in us)
    assert ninguem == []
