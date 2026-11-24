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


def test_item_envenenado_estaciona_so_a_sua_conversa_e_o_replay_restaura_a_ordem():
    from nucleo.infra.relay import RESERVAR

    reservar = RESERVAR.replace(":reserva", "%s")
    sql("UPDATE outbox SET status = 'enviado' WHERE status IN ('pendente', 'enviando')")  # isola o teste
    envenenada, outra = nova_conversa(), nova_conversa()

    def item(conv, seq, status="pendente"):
        sql("INSERT INTO outbox (id_evento, id_conversa, sequencia, destino, payload, status) "
            "VALUES (%s, %s, %s, 'broker', '{}', %s) RETURNING id", uuid.uuid4(), conv, seq, status)
        return sql("SELECT id FROM outbox WHERE id_conversa = %s AND sequencia = %s", conv, seq)[0][0]

    ruim = item(envenenada, 1, "erro")
    depois = [item(envenenada, 2), item(envenenada, 3)]
    livre = item(outra, 1)
    reservados = []
    while (r := sql(reservar, 30)):
        reservados.append(r[0][0])
    assert reservados == [livre]  # a outra conversa segue; a envenenada fica estacionada
    sql("UPDATE outbox SET status = 'pendente', tentativas = 0, proxima_tentativa = now() WHERE id = %s", ruim)
    ordem = []
    while (r := sql(reservar, 30)):
        ordem.append(r[0][0])
        sql("UPDATE outbox SET status = 'enviado' WHERE id = %s", r[0][0])
    assert ordem == [ruim, *depois]  # o replay sai primeiro e os estacionados vêm na ordem


def test_webhook_entregue_cinco_vezes_gera_uma_mensagem():
    from fastapi.testclient import TestClient

    from nucleo.main import app

    corpo = {"canal": "whatsapp", "marca": "infinitepay", "identificador": f"t-{uuid.uuid4().hex[:6]}",
             "conteudo": "meu repasse não caiu", "id_externo": f"x-{uuid.uuid4().hex[:6]}"}
    with TestClient(app) as cliente:
        respostas = [cliente.post("/mensagens", json=corpo).json() for _ in range(5)]
    assert [r["duplicada"] for r in respostas] == [False, True, True, True, True]
    assert sql("SELECT count(*) FROM mensagens WHERE id_externo = %s", corpo["id_externo"])[0][0] == 1


def _regras_ativas_com(cliente, nova_fila: dict | None) -> int:
    regras = cliente.get("/filas/ativa").json()["filas"]
    if nova_fila:
        regras = {**regras, "filas": [nova_fila, *regras["filas"]]}
    numero = cliente.post("/filas/versoes", json={"regras": regras, "criada_por": "teste"})
    assert numero.status_code == 200, numero.text
    return numero.json()["numero"]


def test_operacao_cria_fila_sem_deploy_e_o_proximo_atendimento_cai_nela_e_rollback_em_menos_de_5s():
    import time

    from fastapi.testclient import TestClient

    from nucleo.main import app

    with TestClient(app) as cliente:
        anterior = cliente.get("/filas/ativa").json()["numero"]
        whatsapp = {"id": "ip-whatsapp", "nome": "InfinitePay - WhatsApp", "ordem": 0, "prioridade": 2,
                    "condicoes": {"todas": [{"campo": "marca", "operador": "igual", "valor": "infinitepay"},
                                            {"campo": "canal", "operador": "igual", "valor": "whatsapp"},
                                            {"campo": "origem", "operador": "igual", "valor": "cliente"}]},
                    "atendentes": [{"tipo": "ia", "id": "ia-infinitepay"}, {"tipo": "equipe", "id": "suporte-br"}]}
        nova = _regras_ativas_com(cliente, whatsapp)
        assert cliente.post(f"/filas/versoes/{nova}/ativar").status_code == 200
        r = cliente.post("/mensagens", json={"canal": "whatsapp", "marca": "infinitepay",
                                             "identificador": f"w-{uuid.uuid4().hex[:6]}", "conteudo": "oi",
                                             "id_externo": f"w-{uuid.uuid4().hex[:6]}"}).json()
        assert sql("SELECT id_fila FROM conversas WHERE id = %s", r["id_conversa"])[0][0] == "ip-whatsapp"
        inicio = time.perf_counter()
        assert cliente.post(f"/filas/versoes/{anterior}/ativar").status_code == 200
        assert time.perf_counter() - inicio < 5
        assert cliente.get("/filas/ativa").json()["numero"] == anterior


def test_pedido_de_atendente_escala_mesmo_sem_fila_de_escalas_nas_regras():
    """A escala a pedido do cliente está no código, não nas regras: nenhuma versão a desliga."""
    from fastapi.testclient import TestClient

    from nucleo.main import app

    with TestClient(app) as cliente:
        anterior = cliente.get("/filas/ativa").json()["numero"]
        regras = cliente.get("/filas/ativa").json()["filas"]
        sem_escalas = {**regras, "filas": [f for f in regras["filas"] if not f["id"].startswith("escalas-")]}
        nova = cliente.post("/filas/versoes", json={"regras": sem_escalas, "criada_por": "teste"}).json()["numero"]
        assert cliente.post(f"/filas/versoes/{nova}/ativar").status_code == 200
        ident = f"h-{uuid.uuid4().hex[:6]}"
        conv = cliente.post("/mensagens", json={"canal": "chat", "marca": "infinitepay", "identificador": ident,
                                                "conteudo": "meu repasse não caiu",
                                                "id_externo": f"h-{uuid.uuid4().hex[:6]}"}).json()["id_conversa"]
        a = analista()
        atr = uuid.uuid4()
        sql("INSERT INTO atribuicoes (id, id_conversa, id_atendente) VALUES (%s, %s, %s)", atr, conv, a)
        sql("UPDATE conversas SET estado = 'com_ia', id_atribuicao_atual = %s WHERE id = %s", atr, conv)
        r = cliente.post("/mensagens", json={"canal": "chat", "marca": "infinitepay", "identificador": ident,
                                             "conteudo": "quero falar com um atendente",
                                             "id_externo": f"h-{uuid.uuid4().hex[:6]}"}).json()
        assert r["estado"] == "escalada"
        resumo = sql("SELECT resumo FROM escalas WHERE id_conversa = %s", conv)[0][0]
        assert resumo and resumo.strip()  # toda escala sai com nota de handoff (I7)
        cliente.post(f"/filas/versoes/{anterior}/ativar")


def test_expurgo_apaga_corpos_vencidos_e_preserva_ouvidoria():
    from fastapi.testclient import TestClient

    from nucleo.main import app

    def resolvida_com_mensagem(texto: str) -> uuid.UUID:
        conv = nova_conversa()
        sql("UPDATE conversas SET estado = 'resolvida', resolvida_em = now() - interval '200 days' WHERE id = %s", conv)
        sql("INSERT INTO mensagens (id, id_conversa, autor_tipo, conteudo, canal, seq) VALUES (%s, %s, 'cliente', %s, 'chat', 1)",
            uuid.uuid4(), conv, texto)
        return conv

    comum, ouvidoria = resolvida_com_mensagem("meu cpf é 000"), resolvida_com_mensagem("reclamação formal")
    recente = nova_conversa()
    sql("INSERT INTO mensagens (id, id_conversa, autor_tipo, conteudo, canal, seq) VALUES (%s, %s, 'cliente', 'oi', 'chat', 1)",
        uuid.uuid4(), recente)
    with TestClient(app) as cliente:
        assert cliente.post(f"/painel/conversas/{ouvidoria}/ouvidoria", json={"ouvidoria": True}).status_code == 200
        r = cliente.post("/supervisor/expurgo", params={"dias": 90}).json()
    assert r["mensagens"] >= 1
    assert sql("SELECT conteudo FROM mensagens WHERE id_conversa = %s", comum)[0][0] == "[expurgado]"
    assert sql("SELECT conteudo FROM mensagens WHERE id_conversa = %s", ouvidoria)[0][0] == "reclamação formal"
    assert sql("SELECT conteudo FROM mensagens WHERE id_conversa = %s", recente)[0][0] == "oi"
    assert sql("SELECT count(*) FROM mensagens WHERE id_conversa = %s", comum)[0][0] == 1  # a linha fica


def test_pedido_de_atendente_na_fila_escala_e_informa_tempo_estimado():
    from fastapi.testclient import TestClient

    from nucleo.main import app

    with TestClient(app) as cliente:
        ident = f"e-{uuid.uuid4().hex[:6]}"
        conv = cliente.post("/mensagens", json={"canal": "chat", "marca": "infinitepay", "identificador": ident,
                                                "conteudo": "meu repasse não caiu",
                                                "id_externo": f"e-{uuid.uuid4().hex[:6]}"}).json()["id_conversa"]
        assert sql("SELECT estado FROM conversas WHERE id = %s", conv)[0][0] == "na_fila"  # sem distribuidor aqui
        r = cliente.post("/mensagens", json={"canal": "chat", "marca": "infinitepay", "identificador": ident,
                                             "conteudo": "quero falar com um atendente",
                                             "id_externo": f"e-{uuid.uuid4().hex[:6]}"}).json()
    assert r["estado"] == "escalada"
    eta = sql("SELECT tempo_estimado_s FROM escalas WHERE id_conversa = %s", conv)[0][0]
    assert eta is not None and eta >= 0
    aviso = sql("SELECT payload->>'conteudo' FROM outbox WHERE id_conversa = %s AND destino = 'canal' "
                "ORDER BY sequencia DESC LIMIT 1", conv)[0][0]
    assert "especialista" in aviso and ("min" in aviso or "já vai" in aviso)


def test_sessao_da_jim_nao_le_linhas_da_infinitepay():
    """RLS (migration 0006): mesmo pedindo explicitamente a outra marca, nada volta."""
    from fastapi.testclient import TestClient

    from nucleo.main import app

    conv = nova_conversa()  # infinitepay, com mensagem
    sql("INSERT INTO mensagens (id, id_conversa, autor_tipo, conteudo, canal, seq) "
        "VALUES (%s, %s, 'cliente', 'segredo', 'chat', 1)", uuid.uuid4(), conv)
    with psycopg.connect(f"{BASE}/{NOME}") as c:
        c.execute("SET LOCAL ROLE leitura_marca")
        c.execute("SELECT set_config('app.marca', 'jim', true)")
        assert c.execute("SELECT count(*) FROM conversas WHERE marca = 'infinitepay'").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM mensagens WHERE id_conversa = %s", (conv,)).fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM clientes WHERE marca = 'infinitepay'").fetchone()[0] == 0
        c.rollback()
        c.execute("SET LOCAL ROLE leitura_marca")
        c.execute("SELECT set_config('app.marca', 'infinitepay', true)")
        assert c.execute("SELECT count(*) FROM mensagens WHERE id_conversa = %s", (conv,)).fetchone()[0] == 1
    with TestClient(app) as cliente:
        assert cliente.get(f"/conversas/{conv}", params={"marca": "jim"}).status_code == 404
        assert cliente.get(f"/conversas/{conv}", params={"marca": "infinitepay"}).status_code == 200
        assert all(x["marca"] == "jim" for x in cliente.get("/conversas", params={"marca": "jim"}).json())
