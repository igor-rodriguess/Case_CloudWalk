"""Reconciliador: confere invariantes no banco (docs/implementacao.md, seção 9).

Complementa o juiz das pontas do experimento. Roda sob demanda (/supervisor/reconciliacao)
ou como script: python -m nucleo.reconciliacao
"""

import asyncio
import json

from sqlalchemy import text

from nucleo import config
from nucleo.infra.banco import Sessao

INVARIANTES = {
    "I1_mensagem_sem_desfecho": """
        SELECT m.id FROM mensagens m JOIN conversas c ON c.id = m.id_conversa
        WHERE m.autor_tipo = 'cliente' AND c.estado = 'com_ia'
          AND m.criada_em < now() - make_interval(secs => :prazo)
          AND NOT EXISTS (SELECT 1 FROM mensagens r WHERE r.id_conversa = m.id_conversa
                          AND r.autor_tipo IN ('ia', 'humano') AND r.seq > m.seq)
          AND NOT EXISTS (SELECT 1 FROM agendamentos a WHERE a.id_conversa = m.id_conversa
                          AND a.status = 'pendente' AND a.executar_em > now())
    """,
    "I1b_esperando_humano": """
        SELECT id FROM conversas WHERE estado = 'escalada'
          AND coalesce(na_fila_desde, criada_em) < now() - make_interval(secs => :prazo)
    """,
    "I2_outbox_parada": """
        SELECT id FROM outbox WHERE status IN ('pendente', 'enviando')
          AND criado_em < now() - make_interval(secs => :limite)
    """,
    "I3_resposta_duplicada": """
        SELECT causado_por::text || ':' || sequencia FROM mensagens
        WHERE autor_tipo = 'ia' AND causado_por IS NOT NULL
        GROUP BY causado_por, sequencia HAVING count(*) > 1
    """,
    "I4_resposta_fora_de_dono": """
        SELECT id FROM mensagens WHERE autor_tipo = 'ia'
          AND id_atribuicao_declarada IS DISTINCT FROM id_atribuicao
    """,
    "I5_capacidade": """
        SELECT a.id FROM atendentes a
        WHERE a.tipo = 'humano' AND (a.ativas > a.capacidade OR a.ativas <>
              (SELECT count(*) FROM atribuicoes t WHERE t.id_atendente = a.id AND t.fim IS NULL))
    """,
    "I7_escala_sem_nota": """
        SELECT e.id FROM escalas e WHERE coalesce(trim(e.resumo), '') = ''
    """,
    "I6_conversa_aberta_duplicada": """
        SELECT id_cliente::text || ':' || marca FROM conversas WHERE estado <> 'resolvida'
        GROUP BY id_cliente, marca HAVING count(*) > 1
    """,
}


async def reconciliar() -> dict:
    resultado = {}
    async with Sessao() as s:
        for nome, sql in INVARIANTES.items():
            params = {}
            if ":prazo" in sql:
                params["prazo"] = config.PRAZO_RESPOSTA_S
            if ":limite" in sql:
                params["limite"] = config.OUTBOX_LIMITE_S
            r = await s.execute(text(sql), params)
            refs = [str(x[0]) for x in r.all()]
            resultado[nome] = {"total": len(refs), "exemplos": refs[:10]}
    return resultado


if __name__ == "__main__":
    print(json.dumps(asyncio.run(reconciliar()), indent=2, ensure_ascii=False))
