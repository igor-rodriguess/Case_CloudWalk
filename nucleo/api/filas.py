"""Configuração das filas pela operação, sem deploy: versões imutáveis, validação, ativação
atômica, rollback (reativar uma versão anterior) e simulador do roteador."""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from nucleo.dominio.acoes import rotear_conversa
from nucleo.dominio.roteador import rotear, validar
from nucleo.dominio.transicionar import Ator, auditar
from nucleo.infra.banco import Sessao, unidade
from nucleo.infra.seed import grupos_elegiveis, grupos_existentes

router = APIRouter(prefix="/filas", tags=["filas"])


class NovaVersao(BaseModel):
    regras: dict
    criada_por: str


class Simulacao(BaseModel):
    atendimento: dict
    regras: dict | None = None


@router.get("/versoes", summary="Versões das regras de filas")
async def versoes():
    async with Sessao() as s:
        r = await s.execute(
            text("SELECT numero, ativa, criada_por, criada_em, ativada_em, filas FROM versoes_regras ORDER BY numero DESC")
        )
        return [dict(x) for x in r.mappings().all()]


@router.get("/ativa", summary="Versão ativa")
async def ativa():
    async with Sessao() as s:
        r = await s.execute(text("SELECT numero, filas, ativada_em FROM versoes_regras WHERE ativa"))
        return dict(r.mappings().first())


@router.get("/grupos", summary="Grupos de atendentes que as filas podem usar")
async def grupos():
    async with Sessao() as s:
        return [{"tipo": t, "id": i} for t, i in sorted(await grupos_existentes(s))]


@router.post("/validar", summary="Valida regras sem salvar")
async def validar_regras(regras: dict):
    async with Sessao() as s:
        v = validar(regras, await grupos_existentes(s), await grupos_elegiveis(s))
    return {"valida": v.valida, "erros": v.erros}


@router.post("/versoes", summary="Cria uma versão nova (inativa)")
async def criar(corpo: NovaVersao):
    async with unidade() as s:
        v = validar(corpo.regras, await grupos_existentes(s), await grupos_elegiveis(s))
        if not v.valida:
            raise HTTPException(422, {"erros": v.erros})
        r = await s.execute(
            text("INSERT INTO versoes_regras (filas, criada_por) VALUES (CAST(:f AS jsonb), :p) RETURNING numero"),
            {"f": json.dumps(corpo.regras), "p": corpo.criada_por},
        )
        numero = r.scalar()
        await auditar(s, "versao_regras_criada", Ator("humano"), numero=numero, criada_por=corpo.criada_por)
    return {"numero": numero}


@router.post("/versoes/{numero}/ativar", summary="Ativa uma versão (também serve de rollback)")
async def ativar(numero: int):
    async with unidade() as s:
        r = await s.execute(text("SELECT filas FROM versoes_regras WHERE numero = :n"), {"n": numero})
        regras = r.scalar()
        if regras is None:
            raise HTTPException(404, "versão não existe")
        v = validar(regras, await grupos_existentes(s), await grupos_elegiveis(s))
        if not v.valida:
            raise HTTPException(422, {"erros": v.erros})
        await s.execute(text("SELECT pg_advisory_xact_lock(42)"))
        await s.execute(text("UPDATE versoes_regras SET ativa = false WHERE ativa"))
        await s.execute(
            text("UPDATE versoes_regras SET ativa = true, ativada_em = now() WHERE numero = :n"), {"n": numero}
        )
        ids = {f["id"] for f in regras["filas"] if f.get("ativa", True)}
        orfas = await s.execute(
            text(
                "SELECT * FROM conversas WHERE estado IN ('na_fila', 'escalada') "
                "AND NOT (id_fila = ANY(CAST(:ids AS text[]))) FOR UPDATE SKIP LOCKED"
            ),
            {"ids": list(ids)},
        )
        reroteadas = 0
        for c in orfas.mappings().all():
            await rotear_conversa(s, dict(c))
            reroteadas += 1
        await auditar(s, "versao_regras_ativada", Ator("humano"), numero=numero, reroteadas=reroteadas)
    return {"ativa": numero, "reroteadas": reroteadas}


@router.post("/simular", summary="Simula o roteamento de um atendimento")
async def simular(corpo: Simulacao):
    async with Sessao() as s:
        if corpo.regras is None:
            r = await s.execute(text("SELECT numero, filas FROM versoes_regras WHERE ativa"))
            numero, regras = r.first()
        else:
            numero, regras = 0, corpo.regras
    d = rotear(corpo.atendimento, regras, numero)
    return {"fila": d.fila, "regra": d.regra, "versao": d.versao}
