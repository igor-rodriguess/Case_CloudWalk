"""Juiz nas pontas (docs/implementacao.md, seção 14).

Conta pelo que o cliente enviou (registros do gerador) e pelo que o canal entregou (banco
`canais`). Usa o banco do núcleo só para ligar cada resposta à mensagem do cliente: a resposta
entregue tem `causado_por` = evento enviado ao agente; a linha de `mensagens` da IA com esse
`causado_por` dá a conversa e o `seq`; a mensagem do cliente com o maior `seq` abaixo dá o
`id_externo`. Limitação declarada: supõe uma resposta antes da mensagem seguinte da conversa.
"""

import os
from collections import defaultdict
from statistics import quantiles

import psycopg

NUCLEO_DB = os.getenv("JUIZ_NUCLEO_DB", "postgresql://helpdesk:helpdesk@localhost:5433/helpdesk")
CANAIS_DB = os.getenv("JUIZ_CANAIS_DB", "postgresql://helpdesk:helpdesk@localhost:5433/canais")


def p95(valores):
    if not valores:
        return None
    if len(valores) == 1:
        return valores[0]
    return quantiles(valores, n=20)[18]


def julgar(registros, janela_ini: float, janela_fim: float, falha: dict | None = None) -> tuple[dict, list[dict]]:
    conversas = sorted({r.id_conversa for r in registros if r.id_conversa})
    with psycopg.connect(CANAIS_DB) as c:
        entregas = c.execute(
            "SELECT id_conversa::text, autor, causado_por::text, sequencia, "
            "extract(epoch FROM recebida_em) FROM entregas WHERE id_conversa = ANY(%s::uuid[])",
            (conversas,),
        ).fetchall()
    with psycopg.connect(NUCLEO_DB) as c:
        msgs = c.execute(
            "SELECT id_conversa::text, autor_tipo, causado_por::text, seq, id_externo, id::text "
            "FROM mensagens WHERE id_conversa = ANY(%s::uuid[])",
            (conversas,),
        ).fetchall()
        internas = c.execute(
            """
            SELECT extract(epoch FROM o.enviado_em - m.criada_em)
            FROM outbox o JOIN mensagens m ON m.id::text = o.payload->'dados'->>'id_mensagem'
            WHERE o.id_conversa = ANY(%s::uuid[]) AND o.payload->>'tipo' = 'mensagem.recebida'
              AND o.status = 'enviado'
            """,
            (conversas,),
        ).fetchall()
        # Correspondência exata, quando a outbox existe (OUTBOX_ATIVA = true): o evento que o
        # agente respondeu diz qual mensagem do cliente ele carregava. Com a outbox desligada não
        # há essa linha e vale a regra por ordem (limitação declarada).
        enviados = c.execute(
            """
            SELECT o.payload->>'id_evento', o.payload->>'tipo', o.payload->'dados'
            FROM outbox o
            WHERE o.id_conversa = ANY(%s::uuid[]) AND o.destino = 'broker'
              AND o.payload->>'tipo' IN ('mensagem.recebida', 'conversa.atribuida', 'conversa.devolvida')
            """,
            (conversas,),
        ).fetchall()

    externo_por_id = {id_msg: id_ext for _c, autor, _causa, _seq, id_ext, id_msg in msgs if autor == "cliente"}
    externo_por_evento = {}               # id_evento enviado ao agente -> id_externo da mensagem
    for id_evento, tipo, dados in enviados:
        dados = dados or {}
        if tipo == "mensagem.recebida":
            id_msg = dados.get("id_mensagem")
        else:
            do_cliente = [m for m in dados.get("historico", []) if m.get("autor") == "cliente"]
            id_msg = do_cliente[-1]["id"] if do_cliente else None
        if id_msg in externo_por_id:
            externo_por_evento[id_evento] = externo_por_id[id_msg]

    clientes = defaultdict(list)          # conversa -> [(seq, id_externo)]
    ia_por_causa = {}                     # (conversa, causado_por) -> seq
    for conv, autor, causa, seq, id_ext, _ in msgs:
        if autor == "cliente" and seq is not None:
            clientes[conv].append((seq, id_ext))
        elif autor == "ia" and causa:
            ia_por_causa[(conv, causa)] = seq
    for lista in clientes.values():
        lista.sort()

    contagem_regra = defaultdict(int)     # quantas respostas ligadas por cada regra
    respostas = defaultdict(list)         # id_externo -> [instantes]
    transferencias = defaultdict(list)    # conversa -> [instantes]
    for conv, autor, causa, _seq, quando in entregas:
        quando = float(quando)
        if autor == "sistema":
            transferencias[conv].append(quando)
            continue
        if autor != "ia":
            continue
        if causa in externo_por_evento:
            respostas[externo_por_evento[causa]].append(quando)
            contagem_regra["exata"] += 1
            continue
        contagem_regra["por_ordem"] += 1
        seq_ia = ia_por_causa.get((conv, causa))
        if seq_ia is None:
            continue
        anteriores = [x for x in clientes[conv] if x[0] < seq_ia]
        if anteriores:
            respostas[anteriores[-1][1]].append(quando)

    linhas, esperas = [], []
    contagem = defaultdict(int)
    vistos = set()
    for r in registros:
        e = r.envio
        if e.reenvio or not (janela_ini <= e.t < janela_fim) or e.id_externo in vistos:
            continue
        vistos.add(e.id_externo)
        contagem["enviadas"] += 1
        resp = sorted(respostas.get(e.id_externo, []))
        transf = sorted(transferencias.get(r.id_conversa or "", []))
        if not (200 <= r.status < 300):
            desfecho = "recusada"
        elif resp:
            desfecho = "respondida"
            esperas.append(resp[0] - r.enviado_em)
            contagem["duplicadas"] += len(resp) - 1
        elif any(t > r.enviado_em for t in transf):
            desfecho = "escalada"
        elif any(t <= r.enviado_em for t in transf):
            desfecho = "esperando_humano"
        else:
            desfecho = "perdida"
        contagem[desfecho] += 1
        linhas.append({"id_externo": e.id_externo, "conversa": r.id_conversa, "t": round(e.t, 3),
                       "enviado_em": r.enviado_em, "status": r.status, "desfecho": desfecho,
                       "respostas": len(resp), "espera_s": round(resp[0] - r.enviado_em, 3) if resp else ""})

    recuperacao = None
    if falha:
        atrasadas = [max(respostas[l["id_externo"]]) for l in linhas
                     if falha["parou_em"] <= l["enviado_em"] <= falha["voltou_em"] and respostas.get(l["id_externo"])]
        if atrasadas:
            recuperacao = round(max(atrasadas) - falha["voltou_em"], 1)

    metricas = {
        "enviadas": contagem["enviadas"],
        "recusadas": contagem["recusada"],
        "perdidas": contagem["perdida"],
        "duplicadas": contagem["duplicadas"],
        "escaladas": contagem["escalada"],
        "esperando_humano": contagem["esperando_humano"],
        "respondidas": contagem["respondida"],
        "espera_p95_s": round(p95(esperas), 3) if esperas else None,
        "p95_interna_s": round(p95([float(x[0]) for x in internas]), 3) if internas else None,
        "recuperacao_s": recuperacao,
        "respostas_ligadas_exata": contagem_regra["exata"],
        "respostas_ligadas_por_ordem": contagem_regra["por_ordem"],
    }
    return metricas, linhas
