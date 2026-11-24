"""Distribuidor em laço (docs/implementacao.md 8): uma conversa por transação.

A cada ciclo monta, sem travar, as filas que têm algum grupo com atendente livre. Depois
pega uma conversa por vez (FOR UPDATE SKIP LOCKED), escolhe o atendente (função pura) e
atribui pelo transicionar. Fila lotada não segura as outras.
"""

import asyncio
import logging

from sqlalchemy import text

from nucleo import config
from nucleo.dominio.acoes import contexto_para_ia, regras_ativas
from nucleo.dominio.distribuicao import Candidato, escolher
from nucleo.dominio.transicionar import SISTEMA, Resultado, auditar, novo_evento, transicionar
from nucleo.infra.banco import Sessao, unidade

log = logging.getLogger("distribuidor")

# Pega um lote da fila, na ordem (prioridade da fila, escalada antes, prioridade com
# envelhecimento, chegada), travado com SKIP LOCKED: tarefas em paralelo recebem lotes disjuntos.
# O lote inteiro é atribuído numa transação, cada conversa pelo transicionar sob a sua trava.
# Histórico (testes de carga, 24/11): uma ordenação da fila inteira por conversa derrubava a vazão
# conforme a fila crescia; lote ordenado sem trava fazia as tarefas disputarem as mesmas linhas.
PEGAR_LOTE = """
SELECT c.id, c.id_fila, c.origem FROM conversas c
JOIN unnest(CAST(:filas AS text[]), CAST(:prios AS int[])) AS f(id_fila, prioridade) ON f.id_fila = c.id_fila
WHERE c.estado IN ('na_fila', 'escalada')
ORDER BY f.prioridade DESC,
         (c.origem = 'escalado') DESC,
         coalesce(c.prioridade, 1)
           + floor(extract(epoch FROM now() - coalesce(c.na_fila_desde, c.criada_em)) / :env) DESC,
         coalesce(c.na_fila_desde, c.criada_em)
LIMIT :lote
FOR UPDATE OF c SKIP LOCKED
"""


async def _atendentes(s) -> list[dict]:
    r = await s.execute(text("SELECT * FROM atendentes"))
    return [dict(a) for a in r.mappings().all()]


def _candidatos(fila: dict, atendentes: list[dict], origem: str) -> list[Candidato]:
    out = []
    for i, g in enumerate(fila["atendentes"]):
        if g["tipo"] == "ia" and origem == "escalado":
            continue  # escalada não volta para a IA pelo distribuidor
        for a in atendentes:
            if a["id_equipe"] == g["id"] and (a["tipo"] == "ia") == (g["tipo"] == "ia"):
                out.append(Candidato(a["id"], a["tipo"], i, a["status"] == "disponivel", a["ativas"], a["capacidade"]))
    return out


async def _ciclo() -> int:
    async with Sessao() as s:
        regras, _ = await regras_ativas(s)
        atendentes = await _atendentes(s)
    filas = {f["id"]: f for f in regras["filas"] if f.get("ativa", True)}
    elegiveis = {
        fid: f["prioridade"]
        for fid, f in filas.items()
        if escolher(_candidatos(f, atendentes, "cliente")).id is not None
        or escolher(_candidatos(f, atendentes, "escalado")).id is not None
    }
    atribuidas = 0
    while elegiveis:
        async with unidade() as s:
            r = await s.execute(
                text(PEGAR_LOTE),
                {"filas": list(elegiveis), "prios": list(elegiveis.values()), "env": config.ENVELHECIMENTO_S,
                 "lote": config.DISTRIBUIDOR_LOTE},
            )
            lote = [dict(x) for x in r.mappings().all()]
            if not lote:
                return atribuidas
            for linha in lote:
                if linha["id_fila"] not in elegiveis:
                    continue  # a fila lotou neste lote; a conversa fica para o próximo ciclo
                fila = filas[linha["id_fila"]]
                candidatos = _candidatos(fila, await _atendentes(s), linha["origem"])
                escolha = escolher(candidatos)
                await auditar(
                    s, "decisao_distribuicao", SISTEMA, linha["id"], fila=fila["id"],
                    candidatos=[c.__dict__ for c in candidatos], escolhido=escolha.id, motivo=escolha.motivo,
                )
                if escolha.id is None:
                    elegiveis.pop(linha["id_fila"], None)
                    continue
                tipo = next(c.tipo for c in candidatos if c.id == escolha.id)
                para = "com_ia" if tipo == "ia" else "com_humano"

                async def saidas(s2, c, para=para):
                    if para != "com_ia":
                        return []
                    return [novo_evento("conversa.atribuida", c, await contexto_para_ia(s2, c))]

                resultado, _ = await transicionar(
                    s, linha["id"], para, SISTEMA, id_atendente=escolha.id, id_fila=fila["id"], saidas=saidas
                )
                if resultado == Resultado.SEM_CAPACIDADE:
                    elegiveis.pop(linha["id_fila"], None)
                elif resultado == Resultado.APLICADO:
                    atribuidas += 1
        if len(lote) < config.DISTRIBUIDOR_LOTE:
            return atribuidas
    return atribuidas


async def _tarefa(i: int) -> None:
    while True:
        try:
            await _ciclo()
        except Exception:
            log.exception("distribuidor %s", i)
        await asyncio.sleep(config.DISTRIBUIDOR_INTERVALO_S)


async def laco() -> None:
    """Várias tarefas em paralelo: o SKIP LOCKED garante que duas nunca pegam a mesma conversa.
    Uma tarefa só atendia ~5 conversas novas/s (testes de carga, 23/11)."""
    await asyncio.gather(*(_tarefa(i) for i in range(config.DISTRIBUIDOR_TAREFAS)))
