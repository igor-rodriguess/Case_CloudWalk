"""Painel do analista: fila de escalas, assumir, responder, devolver para a IA e encerrar."""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from nucleo.dominio.acoes import contexto_para_ia
from nucleo.dominio.transicionar import Ator, Resultado, novo_evento, para_canal, transicionar
from nucleo.infra.banco import Sessao, unidade

router = APIRouter(prefix="/painel", tags=["painel do analista"])


class Analista(BaseModel):
    id_atendente: uuid.UUID


class Resposta(Analista):
    conteudo: str = Field(min_length=1)


class Devolucao(Analista):
    nota: str = Field(default="", description="orientação do analista para a IA")


def _checar(resultado: Resultado) -> dict:
    if resultado == Resultado.APLICADO:
        return {"resultado": resultado.value}
    status = {Resultado.INEXISTENTE: 404, Resultado.SEM_CAPACIDADE: 409}.get(resultado, 409)
    raise HTTPException(status_code=status, detail=resultado.value)


@router.get("/atendentes", summary="Atendentes (IA e humanos) com ocupação")
async def atendentes():
    async with Sessao() as s:
        r = await s.execute(
            text("SELECT id, tipo, nome, marca, id_equipe, capacidade, ativas, status FROM atendentes ORDER BY tipo, nome")
        )
        return [dict(a) for a in r.mappings().all()]


@router.get("/fila", summary="Fila de escalas e conversas aguardando humano")
async def fila(marca: str | None = None, equipe: str | None = None):
    async with Sessao() as s:
        r = await s.execute(
            text(
                """
                SELECT c.id, c.marca, c.canal, c.estado, c.categoria, c.prioridade, c.sentimento,
                       c.origem, c.id_fila, c.na_fila_desde,
                       extract(epoch FROM now() - coalesce(c.na_fila_desde, c.criada_em))::int AS espera_s,
                       cl.nome AS cliente,
                       e.motivo, e.resumo, e.fontes, e.reserva
                FROM conversas c
                JOIN clientes cl ON cl.id = c.id_cliente
                LEFT JOIN LATERAL (
                    SELECT motivo, resumo, fontes, reserva FROM escalas
                    WHERE id_conversa = c.id ORDER BY criada_em DESC LIMIT 1) e ON true
                WHERE c.estado IN ('escalada', 'na_fila')
                  AND (CAST(:marca AS text) IS NULL OR c.marca = :marca)
                ORDER BY c.estado = 'escalada' DESC, c.prioridade DESC NULLS LAST, c.na_fila_desde
                LIMIT 200
                """
            ),
            {"marca": marca},
        )
        linhas = [dict(x) for x in r.mappings().all()]
        if equipe:
            regras = (await s.execute(text("SELECT filas FROM versoes_regras WHERE ativa"))).scalar()
            filas_da_equipe = {
                f["id"] for f in regras["filas"] if any(g["id"] == equipe for g in f["atendentes"])
            }
            linhas = [x for x in linhas if x["id_fila"] in filas_da_equipe]
        return linhas


@router.get("/atendentes/{id_atendente}/conversas", summary="Conversas com o atendente")
async def conversas_do_atendente(id_atendente: uuid.UUID):
    async with Sessao() as s:
        r = await s.execute(
            text(
                "SELECT c.id, c.marca, c.canal, c.estado, c.categoria, c.prioridade, cl.nome AS cliente, "
                "c.atualizada_em FROM conversas c JOIN clientes cl ON cl.id = c.id_cliente "
                "WHERE c.id_atendente = :a AND c.estado IN ('com_ia', 'com_humano') ORDER BY c.atualizada_em DESC"
            ),
            {"a": id_atendente},
        )
        return [dict(x) for x in r.mappings().all()]


@router.post("/conversas/{id_conversa}/assumir", summary="Analista assume uma conversa da fila")
async def assumir(id_conversa: uuid.UUID, corpo: Analista):
    async with unidade() as s:
        resultado, _ = await transicionar(
            s, id_conversa, "com_humano", Ator("humano", corpo.id_atendente), id_atendente=corpo.id_atendente,
            motivo="analista_assumiu",
        )
    return _checar(resultado)


async def _dono(s, id_conversa, id_atendente) -> None:
    r = await s.execute(text("SELECT estado, id_atendente FROM conversas WHERE id = :c"), {"c": id_conversa})
    c = r.mappings().first()
    if c is None:
        raise HTTPException(404, "conversa não existe")
    if c["estado"] != "com_humano" or c["id_atendente"] != id_atendente:
        raise HTTPException(409, "conversa não está com este analista")


@router.post("/conversas/{id_conversa}/responder", summary="Analista responde ao cliente")
async def responder(id_conversa: uuid.UUID, corpo: Resposta):
    async with unidade() as s:
        await _dono(s, id_conversa, corpo.id_atendente)

        async def saidas(s2, c):
            return [para_canal(c, "humano", corpo.conteudo)]

        resultado, _ = await transicionar(
            s, id_conversa, None, Ator("humano", corpo.id_atendente),
            mensagem={"autor_tipo": "humano", "id_autor": corpo.id_atendente, "conteudo": corpo.conteudo},
            saidas=saidas,
        )
    return _checar(resultado)


@router.post("/conversas/{id_conversa}/devolver", summary="Analista devolve a conversa para a IA")
async def devolver(id_conversa: uuid.UUID, corpo: Devolucao):
    async with unidade() as s:
        await _dono(s, id_conversa, corpo.id_atendente)
        r = await s.execute(
            text(
                "SELECT a.id FROM atendentes a JOIN conversas c ON c.marca = a.marca "
                "WHERE c.id = :c AND a.tipo = 'ia' LIMIT 1"
            ),
            {"c": id_conversa},
        )
        ia = r.scalar()

        async def saidas(s2, c):
            dados = await contexto_para_ia(s2, c)
            dados.update(motivo="devolvida_pelo_analista", nota_do_analista=corpo.nota)
            return [novo_evento("conversa.devolvida", c, dados)]

        resultado, _ = await transicionar(
            s, id_conversa, "com_ia", Ator("humano", corpo.id_atendente), id_atendente=ia,
            saidas=saidas, motivo="devolvida",
        )
    return _checar(resultado)


@router.post("/conversas/{id_conversa}/encerrar", summary="Analista encerra a conversa")
async def encerrar(id_conversa: uuid.UUID, corpo: Analista):
    async with unidade() as s:
        await _dono(s, id_conversa, corpo.id_atendente)
        resultado, _ = await transicionar(
            s, id_conversa, "resolvida", Ator("humano", corpo.id_atendente), motivo="resolvida"
        )
    return _checar(resultado)
