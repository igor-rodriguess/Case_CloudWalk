"""Leitura de conversas: lista, detalhe com histórico, auditoria, escalas e perfil."""

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from nucleo.dominio.acoes import perfil_operacional
from nucleo.infra.banco import Sessao

router = APIRouter(prefix="/conversas", tags=["conversas"])


@router.get("", summary="Lista de conversas")
async def listar(estado: str | None = None, marca: str | None = None, limite: int = 100):
    async with Sessao() as s:
        r = await s.execute(
            text(
                """
                SELECT c.id, c.marca, c.canal, c.estado, c.categoria, c.prioridade, c.sentimento, c.origem,
                       c.id_fila, c.id_atendente, a.nome AS atendente, cl.nome AS cliente,
                       c.criada_em, c.atualizada_em
                FROM conversas c JOIN clientes cl ON cl.id = c.id_cliente
                LEFT JOIN atendentes a ON a.id = c.id_atendente
                WHERE (CAST(:estado AS text) IS NULL OR c.estado = :estado)
                  AND (CAST(:marca AS text) IS NULL OR c.marca = :marca)
                ORDER BY c.atualizada_em DESC LIMIT :limite
                """
            ),
            {"estado": estado, "marca": marca, "limite": min(limite, 500)},
        )
        return [dict(x) for x in r.mappings().all()]


@router.get("/{id_conversa}", summary="Conversa com mensagens, auditoria, escalas e perfil")
async def detalhe(id_conversa: uuid.UUID):
    async with Sessao() as s:
        r = await s.execute(
            text(
                "SELECT c.*, cl.nome AS cliente, a.nome AS atendente FROM conversas c "
                "JOIN clientes cl ON cl.id = c.id_cliente LEFT JOIN atendentes a ON a.id = c.id_atendente "
                "WHERE c.id = :id"
            ),
            {"id": id_conversa},
        )
        c = r.mappings().first()
        if c is None:
            raise HTTPException(404, "conversa não existe")
        conversa = dict(c)
        mensagens = await s.execute(
            text(
                "SELECT id, autor_tipo, id_autor, conteudo, canal, id_externo, seq, criada_em "
                "FROM mensagens WHERE id_conversa = :id ORDER BY seq NULLS FIRST, criada_em"
            ),
            {"id": id_conversa},
        )
        eventos = await s.execute(
            text(
                "SELECT tipo, ator_tipo, id_ator, id_atribuicao, payload, criado_em FROM eventos "
                "WHERE id_conversa = :id ORDER BY id"
            ),
            {"id": id_conversa},
        )
        escalas = await s.execute(
            text("SELECT motivo, resumo, fontes, reserva, prioridade, criada_em FROM escalas "
                 "WHERE id_conversa = :id ORDER BY criada_em"),
            {"id": id_conversa},
        )
        return {
            "conversa": conversa,
            "mensagens": [dict(x) for x in mensagens.mappings().all()],
            "auditoria": [dict(x) for x in eventos.mappings().all()],
            "escalas": [dict(x) for x in escalas.mappings().all()],
            "perfil": await perfil_operacional(s, conversa),
        }
