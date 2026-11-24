"""Dados iniciais sintéticos: atendentes (IA e humanos por equipe) e a versão 1 das filas."""

import json

from sqlalchemy import text

from nucleo import config
from nucleo.infra.banco import unidade

ATENDENTES = [
    ("ia", "Claudio (IA)", "infinitepay", "ia-infinitepay"),
    ("ia", "JIM (IA)", "jim", "ia-jim"),
    ("humano", "Ana Souza", "infinitepay", "suporte-br"),
    ("humano", "Bruno Lima", "infinitepay", "suporte-br"),
    ("humano", "Carla Dias", "infinitepay", "credito-br"),
    ("humano", "Dana Smith", "jim", "support-us"),
    ("humano", "Evan Brooks", "jim", "support-us"),
]

FILAS_V1 = {
    "fila_padrao": "padrao",
    "filas": [
        {"id": "escalas-infinitepay", "nome": "InfinitePay - Escalas", "ordem": 1, "prioridade": 3,
         "ativa": True, "ao_abrir_disjuntor": "reter",
         "condicoes": {"todas": [{"campo": "origem", "operador": "igual", "valor": "escalado"},
                                 {"campo": "marca", "operador": "igual", "valor": "infinitepay"}]},
         "atendentes": [{"tipo": "equipe", "id": "suporte-br"}, {"tipo": "equipe", "id": "credito-br"}]},
        {"id": "escalas-jim", "nome": "JIM - Escalations", "ordem": 2, "prioridade": 3, "ativa": True,
         "ao_abrir_disjuntor": "reter",
         "condicoes": {"todas": [{"campo": "origem", "operador": "igual", "valor": "escalado"},
                                 {"campo": "marca", "operador": "igual", "valor": "jim"}]},
         "atendentes": [{"tipo": "equipe", "id": "support-us"}]},
        {"id": "infinitepay-fraude", "nome": "InfinitePay - Fraude (só humanos)", "ordem": 3,
         "prioridade": 3, "ativa": True, "ao_abrir_disjuntor": "transbordar",
         "condicoes": {"todas": [{"campo": "marca", "operador": "igual", "valor": "infinitepay"},
                                 {"campo": "categoria", "operador": "igual", "valor": "fraude"}]},
         "atendentes": [{"tipo": "equipe", "id": "suporte-br"}]},
        {"id": "infinitepay-credito", "nome": "InfinitePay - Crédito", "ordem": 4, "prioridade": 2,
         "ativa": True, "ao_abrir_disjuntor": "reter",
         "condicoes": {"todas": [{"campo": "marca", "operador": "igual", "valor": "infinitepay"},
                                 {"campo": "categoria", "operador": "igual", "valor": "credito"}]},
         "atendentes": [{"tipo": "ia", "id": "ia-infinitepay"}, {"tipo": "equipe", "id": "credito-br"}]},
        {"id": "infinitepay-geral", "nome": "InfinitePay - Geral", "ordem": 5, "prioridade": 1,
         "ativa": True, "ao_abrir_disjuntor": "reter",
         "condicoes": {"todas": [{"campo": "marca", "operador": "igual", "valor": "infinitepay"}]},
         "atendentes": [{"tipo": "ia", "id": "ia-infinitepay"}, {"tipo": "equipe", "id": "suporte-br"}]},
        {"id": "jim-geral", "nome": "JIM - General", "ordem": 6, "prioridade": 1, "ativa": True,
         "ao_abrir_disjuntor": "reter",
         "condicoes": {"todas": [{"campo": "marca", "operador": "igual", "valor": "jim"}]},
         "atendentes": [{"tipo": "ia", "id": "ia-jim"}, {"tipo": "equipe", "id": "support-us"}]},
        {"id": "padrao", "nome": "Padrão", "ordem": 99, "prioridade": 1, "ativa": True,
         "ao_abrir_disjuntor": "reter", "condicoes": {},
         "atendentes": [{"tipo": "equipe", "id": "suporte-br"}]},
    ],
}


async def semear() -> None:
    async with unidade() as s:
        # Vários processos sobem juntos: a trava garante uma semeadura só.
        await s.execute(text("SELECT pg_advisory_xact_lock(7)"))
        ja = (await s.execute(text("SELECT count(*) FROM atendentes"))).scalar()
        if ja:
            return
        for tipo, nome, marca, equipe in ATENDENTES:
            cap = config.CAPACIDADE_IA if tipo == "ia" else config.CAPACIDADE_HUMANO
            await s.execute(
                text(
                    "INSERT INTO atendentes (tipo, nome, marca, id_equipe, capacidade) "
                    "VALUES (:t, :n, :m, :e, :c)"
                ),
                {"t": tipo, "n": nome, "m": marca, "e": equipe, "c": cap},
            )
        await s.execute(
            text(
                "INSERT INTO versoes_regras (filas, ativa, criada_por, ativada_em) "
                "VALUES (CAST(:f AS jsonb), true, 'seed', now())"
            ),
            {"f": json.dumps(FILAS_V1)},
        )


async def grupos_existentes(s) -> set[tuple[str, str]]:
    r = await s.execute(text("SELECT tipo, id_equipe FROM atendentes"))
    grupos = set()
    for tipo, equipe in r.all():
        grupos.add(("ia" if tipo == "ia" else "equipe", equipe))
    return grupos


async def grupos_elegiveis(s) -> set[tuple[str, str]]:
    """Grupos com pelo menos um atendente que pode receber conversa (capacidade > 0)."""
    r = await s.execute(text("SELECT DISTINCT tipo, id_equipe FROM atendentes WHERE capacidade > 0"))
    return {("ia" if tipo == "ia" else "equipe", equipe) for tipo, equipe in r.all()}
