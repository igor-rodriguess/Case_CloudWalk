"""Entrada dos canais simulados (chat, WhatsApp, e-mail).

Idempotente pelo `id_externo` do canal: a chave entra na inbox (consumidor "entrada").
Reenvio do mesmo `id_externo` responde 200 sem efeito. Com INBOX_ATIVA desligada (ablação),
o reenvio vira mensagem nova com o mesmo `id_externo` gravado.
"""

import uuid
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from contrato.ids import NAMESPACE_HELPDESK
from nucleo import config
from nucleo.dominio.acoes import escalar, rotear_conversa
from nucleo.dominio.transicionar import Ator, Resultado, auditar, novo_evento, transicionar
from nucleo.dominio.triagem import pede_humano, triar
from nucleo.infra.banco import unidade

router = APIRouter(tags=["canais"])


class MensagemEntrada(BaseModel):
    canal: Literal["chat", "whatsapp", "email"]
    marca: Literal["infinitepay", "jim"]
    identificador: str = Field(description="id do app, telefone ou e-mail do lojista")
    conteudo: str = Field(min_length=1)
    nome: str | None = Field(default=None, description="nome sintético, usado só no primeiro contato")
    id_externo: str | None = Field(default=None, description="id da mensagem no canal; gerado se ausente")


class MensagemAceita(BaseModel):
    id_conversa: uuid.UUID | None
    id_mensagem: uuid.UUID | None
    duplicada: bool
    estado: str | None


def chave_entrada(canal: str, id_externo: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE_HELPDESK, f"entrada:{canal}:{id_externo}")


async def _cliente(s, m: MensagemEntrada) -> uuid.UUID:
    r = await s.execute(
        text("SELECT id_cliente FROM identidades WHERE canal = :c AND identificador = :i AND marca = :m"),
        {"c": m.canal, "i": m.identificador, "m": m.marca},
    )
    existente = r.scalar()
    if existente:
        return existente
    novo = uuid.uuid4()
    await s.execute(
        text("INSERT INTO clientes (id, marca, nome, segmento) VALUES (:id, :m, :n, 'pme')"),
        {"id": novo, "m": m.marca, "n": m.nome or f"Lojista {m.identificador[-4:]}"},
    )
    await s.execute(
        text("INSERT INTO identidades (canal, identificador, marca, id_cliente) VALUES (:c, :i, :m, :id)"),
        {"c": m.canal, "i": m.identificador, "m": m.marca, "id": novo},
    )
    return novo


async def _processar(s, m: MensagemEntrada, id_externo: str) -> MensagemAceita:
    ator = Ator("cliente")
    id_cliente = await _cliente(s, m)
    r = await s.execute(
        text(
            # FOR UPDATE: se a conversa for resolvida enquanto esperamos a trava, o Postgres reavalia
            # o filtro e ela não volta; a mensagem abre conversa nova em vez de cair numa resolvida.
            "SELECT id, estado FROM conversas WHERE id_cliente = :c AND marca = :m AND estado <> 'resolvida' "
            "ORDER BY criada_em DESC LIMIT 1 FOR UPDATE"
        ),
        {"c": id_cliente, "m": m.marca},
    )
    aberta = r.mappings().first()
    mensagem = {"autor_tipo": "cliente", "conteudo": m.conteudo, "canal": m.canal, "id_externo": id_externo}

    if aberta is None:
        t = triar(m.conteudo, m.marca)
        id_conversa = uuid.uuid4()
        await s.execute(
            text(
                "INSERT INTO conversas (id, id_cliente, marca, canal, estado, categoria, prioridade, "
                "sentimento, idioma) VALUES (:id, :cli, :m, :canal, 'nova', :cat, :p, :sent, :idi)"
            ),
            {"id": id_conversa, "cli": id_cliente, "m": m.marca, "canal": m.canal, "cat": t.categoria,
             "p": t.prioridade, "sent": t.sentimento, "idi": t.idioma},
        )
        await auditar(s, "triagem", ator, id_conversa, categoria=t.categoria, prioridade=t.prioridade,
                      sentimento=t.sentimento, idioma=t.idioma)
        r2 = await s.execute(text("SELECT * FROM conversas WHERE id = :id FOR UPDATE"), {"id": id_conversa})
        await rotear_conversa(s, dict(r2.mappings().first()), ator)
        _, c = await transicionar(s, id_conversa, "na_fila", Ator("sistema"), mensagem=mensagem)
        return MensagemAceita(id_conversa=id_conversa, id_mensagem=c["_id_mensagem"], duplicada=False,
                              estado=c["estado"])

    id_conversa = aberta["id"]

    async def saidas(s2, c):
        if c["estado"] != "com_ia":
            return []  # na fila ou com humano: a mensagem fica no histórico
        dados = {"id_mensagem": str(c["_id_mensagem"]), "conteudo": m.conteudo, "canal": m.canal}
        return [novo_evento("mensagem.recebida", c, dados)]

    resultado, c = await transicionar(s, id_conversa, None, ator, mensagem=mensagem, saidas=saidas)
    if resultado == Resultado.APLICADO and c["estado"] == "com_ia" and pede_humano(m.conteudo):
        await escalar(s, id_conversa, ator, "pedido_do_cliente", id_atribuicao=c["id_atribuicao_atual"],
                      causado_por=chave_entrada(m.canal, id_externo))
        c["estado"] = "escalada"
    return MensagemAceita(id_conversa=id_conversa, id_mensagem=c.get("_id_mensagem"), duplicada=False,
                          estado=c["estado"])


@router.post("/mensagens", response_model=MensagemAceita, summary="Mensagem do lojista por um canal")
async def receber(m: MensagemEntrada) -> MensagemAceita:
    id_externo = m.id_externo or str(uuid.uuid4())
    for tentativa in range(2):  # conversa nova concorrente: o índice único garante uma só
        try:
            async with unidade() as s:
                if config.INBOX_ATIVA:
                    r = await s.execute(
                        text(
                            "INSERT INTO eventos_processados (consumidor, id_evento) VALUES ('entrada', :e) "
                            "ON CONFLICT DO NOTHING RETURNING 1"
                        ),
                        {"e": chave_entrada(m.canal, id_externo)},
                    )
                    if r.first() is None:
                        return MensagemAceita(id_conversa=None, id_mensagem=None, duplicada=True, estado=None)
                return await _processar(s, m, id_externo)
        except IntegrityError:
            if tentativa == 1:
                raise
    raise RuntimeError("inalcançável")
