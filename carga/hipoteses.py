"""Hipóteses H2 e H3 (roteiro de validação de 24/11), contra o ambiente no ar.

H3 (handoff): 1.000 pedidos de atendente; 100% chegam ao humano com nota de handoff e com o
tempo estimado informado ao cliente.

H2 (robustez): carga com 20% de reenvios do canal (mesmo id_externo), 1% de mensagens
envenenadas (o canal recusa a resposta delas até o supervisor liberar) e o relay derrubado por
30 s no meio. Critério: zero respostas duplicadas ao cliente e zero violações de ordem (cada
conversa recebe as saídas na ordem em que o núcleo as gravou), e as envenenadas saem depois do
reprocessamento, na ordem.

Uso (de fora do Docker, porque derruba e sobe contêineres):
    python -m carga.hipoteses H3
    python -m carga.hipoteses H2
"""

import asyncio
import json
import os
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import psycopg

NUCLEO = os.getenv("CARGA_NUCLEO", "http://localhost:8000")
CANAIS = os.getenv("CARGA_CANAIS", "http://localhost:8310")
NUCLEO_DB = os.getenv("JUIZ_NUCLEO_DB", "postgresql://helpdesk:helpdesk@localhost:5433/helpdesk")
CANAIS_DB = os.getenv("JUIZ_CANAIS_DB", "postgresql://helpdesk:helpdesk@localhost:5433/canais")
RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "resultados" / "hipoteses"


def salvar(nome: str, dados: dict) -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    caminho = SAIDA / f"{nome}-{int(time.time())}.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2, default=str), "utf-8")
    print(json.dumps(dados, ensure_ascii=False, indent=2, default=str))


async def enviar(h, sem, corpo):
    async with sem:
        for _ in range(5):
            try:
                r = await h.post(f"{NUCLEO}/mensagens", json=corpo, timeout=30)
                return r.json()
            except httpx.HTTPError:
                await asyncio.sleep(1)
        return None


# ---------------------------------------------------------------- H3
async def h3(n: int = 1000) -> dict:
    rodada = f"H3-{int(time.time())}"
    sem = asyncio.Semaphore(15)
    async with httpx.AsyncClient() as h:
        corpos = [{"canal": random.choice(["chat", "whatsapp", "email"]),
                   "marca": "jim" if i % 5 == 0 else "infinitepay", "identificador": f"{rodada}-c{i}",
                   "conteudo": "I want to talk to a human" if i % 5 == 0 else "quero falar com um atendente",
                   "id_externo": f"{rodada}-m{i}"} for i in range(n)]
        respostas = await asyncio.gather(*(enviar(h, sem, c) for c in corpos))
    convs = [r["id_conversa"] for r in respostas if r and r.get("id_conversa")]
    await asyncio.sleep(10)  # o relay entrega o aviso de transferência ao canal
    with psycopg.connect(NUCLEO_DB) as c:
        esc = c.execute(
            "SELECT e.id_conversa::text, e.resumo, e.tempo_estimado_s FROM escalas e "
            "WHERE e.id_conversa = ANY(%s::uuid[])", (convs,)).fetchall()
    with psycopg.connect(CANAIS_DB) as c:
        avisos = c.execute(
            "SELECT id_conversa::text, conteudo FROM entregas WHERE autor = 'sistema' "
            "AND id_conversa = ANY(%s::uuid[])", (convs,)).fetchall()
    por_conv = {x[0]: x for x in esc}
    com_eta = {cv for cv, txt in avisos if "min" in txt or "já vai" in txt or "shortly" in txt}
    resultado = {
        "hipotese": "H3", "pedidos": n, "aceitos": len(convs),
        "escaladas": len(por_conv),
        "com_nota_de_handoff": sum(1 for x in por_conv.values() if x[1] and x[1].strip()),
        "com_tempo_estimado_gravado": sum(1 for x in por_conv.values() if x[2] is not None),
        "aviso_com_tempo_entregue_ao_cliente": len(com_eta & set(convs)),
        "tempo_estimado_s": {"min": min((x[2] for x in por_conv.values() if x[2] is not None), default=None),
                             "max": max((x[2] for x in por_conv.values() if x[2] is not None), default=None)},
    }
    resultado["passa"] = (resultado["escaladas"] == resultado["com_nota_de_handoff"]
                          == resultado["com_tempo_estimado_gravado"]
                          == resultado["aviso_com_tempo_entregue_ao_cliente"] == n)
    salvar("H3", resultado)
    return resultado


# ---------------------------------------------------------------- H2
def docker(*args) -> None:
    subprocess.run(["docker", "compose", *args], cwd=RAIZ, check=True, capture_output=True)


async def h2(conversas: int = 400, mensagens: int = 5, intervalo_s: float = 8.0) -> dict:
    rodada = f"H2-{int(time.time())}"
    rnd = random.Random(11)
    envenenadas = set(rnd.sample(range(conversas * mensagens), max(1, conversas * mensagens // 100)))
    agenda = []
    for c in range(conversas):
        for k in range(mensagens):
            i = c * mensagens + k
            t = k * intervalo_s + rnd.uniform(0, intervalo_s)
            texto = "meu repasse não caiu #veneno" if i in envenenadas else rnd.choice(
                ["meu repasse não caiu", "quero saber meu saldo", "a maquininha não liga", "obrigado"])
            corpo = {"canal": "chat", "marca": "infinitepay", "identificador": f"{rodada}-c{c}", "conteudo": texto,
                     "id_externo": f"{rodada}-c{c}-m{k}"}
            agenda.append((t, corpo))
            if rnd.random() < 0.20:  # reenvio do canal: mesma mensagem, mesmo id_externo
                agenda.append((t + rnd.uniform(0.1, 3), corpo))
    agenda.sort(key=lambda x: x[0])
    async with httpx.AsyncClient() as h:
        await h.post(f"{CANAIS}/modo", json={"modo": "normal", "recusar": "#veneno"})
    sem = asyncio.Semaphore(15)
    inicio = time.time()
    queda = {}

    async def derrubar_relay():
        await asyncio.sleep(agenda[-1][0] / 2)
        queda["parou"] = time.time()
        docker("stop", "trabalhador")
        await asyncio.sleep(30)
        docker("start", "trabalhador")
        queda["voltou"] = time.time()

    async def no_tempo(h, t, corpo):
        await asyncio.sleep(max(0, inicio + t - time.time()))
        return await enviar(h, sem, corpo)

    async with httpx.AsyncClient() as h:
        tarefa = asyncio.create_task(derrubar_relay())
        respostas = await asyncio.gather(*(no_tempo(h, t, c) for t, c in agenda))
        await tarefa
    reenvios_absorvidos = sum(1 for r in respostas if r and r.get("duplicada"))
    await asyncio.sleep(60)  # o relay esgota as tentativas das envenenadas e drena o resto
    with psycopg.connect(NUCLEO_DB) as c:
        convs = [r[0] for r in c.execute(
            "SELECT DISTINCT m.id_conversa::text FROM mensagens m WHERE m.id_externo LIKE %s", (f"{rodada}-%",))]
        em_erro = [r[0] for r in c.execute(
            "SELECT id FROM outbox WHERE status = 'erro' AND id_conversa = ANY(%s::uuid[])", (convs,))]
        estacionados = c.execute(
            "SELECT count(*) FROM outbox o WHERE o.status = 'pendente' AND o.id_conversa = ANY(%s::uuid[]) "
            "AND EXISTS (SELECT 1 FROM outbox p WHERE p.id_conversa = o.id_conversa AND p.destino = o.destino "
            "AND p.sequencia < o.sequencia AND p.status = 'erro')", (convs,)).fetchone()[0]
    # o supervisor corrige o canal e reprocessa a fila de erros
    async with httpx.AsyncClient() as h:
        await h.post(f"{CANAIS}/modo", json={"modo": "normal", "recusar": None})
        for i in em_erro:
            await h.post(f"{NUCLEO}/outbox/{i}/reprocessar")
    for _ in range(90):  # espera drenar (retentativas com recuo de até 60 s)
        with psycopg.connect(NUCLEO_DB) as c:
            if c.execute("SELECT count(*) FROM outbox WHERE status <> 'enviado' AND id_conversa = ANY(%s::uuid[])",
                         (convs,)).fetchone()[0] == 0:
                break
        await asyncio.sleep(2)
    with psycopg.connect(NUCLEO_DB) as c:
        ordem_outbox = {}
        for cv, ev, seq in c.execute(
                "SELECT id_conversa::text, id_evento::text, sequencia FROM outbox "
                "WHERE destino = 'canal' AND id_conversa = ANY(%s::uuid[])", (convs,)):
            ordem_outbox[ev] = (cv, seq)
        pendentes_fim = c.execute("SELECT count(*) FROM outbox WHERE status <> 'enviado' "
                                  "AND id_conversa = ANY(%s::uuid[])", (convs,)).fetchone()[0]
        respostas_ia = c.execute(
            "SELECT causado_por::text, sequencia, count(*) FROM mensagens WHERE autor_tipo = 'ia' "
            "AND id_conversa = ANY(%s::uuid[]) GROUP BY 1, 2 HAVING count(*) > 1", (convs,)).fetchall()
    with psycopg.connect(CANAIS_DB) as c:
        entregas = c.execute("SELECT id_conversa::text, id_evento::text, id FROM entregas "
                             "WHERE id_conversa = ANY(%s::uuid[]) ORDER BY id", (convs,)).fetchall()
        absorvidas = c.execute("SELECT count(*) FROM duplicatas_absorvidas WHERE id_conversa = ANY(%s::uuid[])",
                               (convs,)).fetchone()[0]
    ultima, violacoes = {}, 0
    for cv, ev, _id in entregas:
        seq = ordem_outbox.get(ev, (cv, None))[1]
        if seq is None:
            continue
        if cv in ultima and seq < ultima[cv]:
            violacoes += 1
        ultima[cv] = seq
    ids_entregues = [e[1] for e in entregas]
    resultado = {
        "hipotese": "H2", "conversas": len(convs), "mensagens": conversas * mensagens,
        "reenvios_do_canal": len(agenda) - conversas * mensagens, "reenvios_absorvidos_na_entrada": reenvios_absorvidos,
        "envenenadas": len(envenenadas), "itens_em_erro_antes_do_replay": len(em_erro),
        "estacionados_atras_deles": estacionados,
        "relay_fora_s": round(queda.get("voltou", 0) - queda.get("parou", 0), 1),
        "entregas_ao_cliente": len(entregas),
        "entregas_duplicadas_ao_cliente": len(ids_entregues) - len(set(ids_entregues)),
        "respostas_duplicadas_da_ia": len(respostas_ia),
        "reentregas_do_relay_absorvidas_no_canal": absorvidas,
        "violacoes_de_ordem": violacoes,
        "saidas_pendentes_no_fim": pendentes_fim,
    }
    resultado["passa"] = (resultado["entregas_duplicadas_ao_cliente"] == 0 and resultado["respostas_duplicadas_da_ia"] == 0
                          and violacoes == 0 and pendentes_fim == 0)
    salvar("H2", resultado)
    return resultado


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    alvo = sys.argv[1] if len(sys.argv) > 1 else "H3"
    asyncio.run(h3() if alvo == "H3" else h2())
