"""Agente mock: faz o papel do agente de IA da CloudWalk (fora do escopo do projeto).

Consome `helpdesk.para-agente`. Numa transação do próprio banco grava a inbox e as respostas
com `publicar_em = agora + latência`; confirma o offset; um laço publica as vencidas. Assim a
latência simulada não serializa a partição. Ids por id_derivado: reprocessar dá o mesmo id.
Devolve o `id_atribuicao` recebido e preenche `causado_por`.
"""

import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal

import psycopg
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from fastapi import FastAPI
from pydantic import BaseModel

from contrato import Envelope, id_derivado, pendentes_do_cliente

KAFKA = os.getenv("KAFKA_BOOTSTRAP", "localhost:19092")
BANCO = os.getenv("MOCK_DATABASE_URL", "postgresql://helpdesk:helpdesk@localhost:5433/agente_mock")
LATENCIA_MS = int(os.getenv("LATENCIA_MS", 800))
TIMEOUT_AGENTE_S = int(os.getenv("TIMEOUT_AGENTE_S", 30))
MOCK_TROCAS = int(os.getenv("MOCK_TROCAS", 6))
IDA, VOLTA = "helpdesk.para-agente", "agente.para-helpdesk"

logging.basicConfig(level=logging.INFO, format='{"servico":"agente_mock","nivel":"%(levelname)s","msg":"%(message)s"}')
log = logging.getLogger("mock")
estado = {"modo": os.getenv("MOCK_MODO", "normal")}

ESCALA = r"\bhumano\b|\batendente\b|irritad|absurdo|p[eé]ssimo|processar|procon|\bhuman\b|angry|lawyer|terrible"
RESPOSTAS = {
    "pt": [
        "Oi! Sou o Claudio, assistente da InfinitePay. Já estou olhando o seu caso.",
        "Encontrei as informações da sua conta. Pode me confirmar a data?",
        "Obrigado. Verifiquei aqui e o processamento está em andamento.",
        "Consegui ajustar. Deve refletir em até 1 hora útil.",
        "Algo mais em que eu possa ajudar?",
        "Fico feliz em ajudar. Vou encerrar o atendimento por aqui.",
    ],
    "en": [
        "Hi! I'm JIM, your assistant. I'm already looking into this.",
        "I found your account details. Could you confirm the date?",
        "Thanks. I checked and the processing is underway.",
        "Done. It should show up within one business hour.",
        "Anything else I can help with?",
        "Glad to help. I'll close this conversation now.",
    ],
}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS inbox (id_evento uuid PRIMARY KEY, recebido_em timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS trocas (id_conversa uuid PRIMARY KEY, n int NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS respostas (
    id_evento uuid PRIMARY KEY, id_conversa uuid NOT NULL, payload jsonb NOT NULL,
    publicar_em timestamptz NOT NULL, publicada boolean NOT NULL DEFAULT false);
CREATE INDEX IF NOT EXISTS ix_respostas_pendentes ON respostas (publicar_em) WHERE NOT publicada;
"""


def _evento(tipo: str, origem: Envelope, dados: dict, sequencia: int = 0) -> dict:
    return {
        "versao": "1.0",
        "id_evento": str(id_derivado(origem.id_evento, tipo, sequencia)),
        "tipo": tipo,
        "id_conversa": str(origem.id_conversa),
        "id_atribuicao": str(origem.id_atribuicao) if origem.id_atribuicao else None,
        "causado_por": str(origem.id_evento),
        "marca": origem.marca,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dados": dados,
    }


def _texto_cliente(env: Envelope) -> tuple[str, str | None]:
    if env.tipo == "mensagem.recebida":
        return env.dados.get("conteudo", ""), env.dados.get("id_mensagem")
    historico = env.dados.get("historico") or []
    do_cliente = [m for m in historico if m.get("autor") == "cliente"]
    if not do_cliente:
        return "", None
    return do_cliente[-1].get("conteudo", ""), do_cliente[-1].get("id")


def respostas_devidas(env: Envelope) -> int:
    """Quantas mensagens o evento pede responder. Na atribuição, uma por mensagem do cliente
    que chegou enquanto a conversa esperava na fila (todas vêm no histórico); senão, uma."""
    if env.tipo == "conversa.atribuida":
        return max(1, len(pendentes_do_cliente(env.dados.get("historico") or [])))
    return 1


def decidir(env: Envelope, trocas: int) -> list[dict]:
    """`trocas` já conta as respostas deste evento: as frases saem das posições anteriores."""
    if env.tipo not in ("conversa.atribuida", "mensagem.recebida", "conversa.devolvida"):
        return []
    idioma = "en" if env.marca == "jim" else "pt"
    texto, id_msg = _texto_cliente(env)
    # Na devolução o humano já tratou o pedido: não reavalia a escala sobre a mensagem antiga.
    if env.tipo != "conversa.devolvida" and re.search(ESCALA, texto.lower()):
        resumo = (
            f"Cliente pede atendimento humano ou demonstra irritação. Última mensagem: \"{texto[:200]}\""
        )
        return [_evento("conversa.escalada", env, {
            "motivo": "cliente_irritado", "resumo": resumo, "prioridade_sugerida": 3,
            "fontes": [id_msg] if id_msg else [],
        })]
    frases = RESPOSTAS[idioma]
    n = respostas_devidas(env)
    saida = []
    for i in range(n):  # sequencia i responde a i-ésima mensagem pendente (contrato.historico)
        frase = frases[min(trocas - n + i, len(frases) - 1)]
        if "#veneno" in texto:  # experimento H2: a resposta carrega a marca e o canal a recusa
            frase += " #veneno"
        saida.append(_evento("mensagem.enviada", env, {"conteudo": frase, "sequencia": i}, sequencia=i))
    if trocas >= MOCK_TROCAS:
        saida.append(_evento("conversa.resolvida", env, {"resumo": "Resolvido pelo agente."}))
    return saida


async def _tratar(conn, env: Envelope) -> None:
    async with conn.transaction():
        cur = await conn.execute(
            "INSERT INTO inbox (id_evento) VALUES (%s) ON CONFLICT DO NOTHING RETURNING 1", (env.id_evento,)
        )
        if await cur.fetchone() is None:
            return  # repetido
        cur = await conn.execute(
            "INSERT INTO trocas (id_conversa, n) VALUES (%s, %s) "
            "ON CONFLICT (id_conversa) DO UPDATE SET n = trocas.n + EXCLUDED.n RETURNING n",
            (env.id_conversa, respostas_devidas(env)),
        )
        trocas = (await cur.fetchone())[0]
        atraso = LATENCIA_MS / 1000
        if estado["modo"] == "lento":
            atraso = TIMEOUT_AGENTE_S + 5
        publicar_em = datetime.now(timezone.utc) + timedelta(seconds=atraso)
        for i, ev in enumerate(decidir(env, trocas)):
            await conn.execute(
                "INSERT INTO respostas (id_evento, id_conversa, payload, publicar_em) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT DO NOTHING",
                (ev["id_evento"], ev["id_conversa"], json.dumps(ev), publicar_em + timedelta(milliseconds=i)),
            )


async def consumir() -> None:
    conexoes: dict = {}
    consumidor = AIOKafkaConsumer(
        IDA, bootstrap_servers=KAFKA, group_id="agente-mock", enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    await consumidor.start()
    try:
        while True:
            if estado["modo"] == "fora":
                if consumidor.assignment():
                    consumidor.pause(*consumidor.assignment())
                await asyncio.sleep(0.5)
                continue
            if consumidor.paused():
                consumidor.resume(*consumidor.paused())
            lotes = await consumidor.getmany(timeout_ms=500, max_records=500)

            async def particao(tp, mensagens):
                # Partições em paralelo, cada uma com a sua conexão; dentro dela, em ordem (a chave
                # é a conversa). Antes era tudo em série e o mock virava o gargalo sob carga.
                if tp not in conexoes:
                    conexoes[tp] = await psycopg.AsyncConnection.connect(BANCO, autocommit=True)
                ultimo_ok = None
                for msg in mensagens:
                    try:
                        env = Envelope.model_validate_json(msg.value)
                    except Exception:
                        log.warning("evento inválido ignorado no offset %s", msg.offset)
                        ultimo_ok = msg.offset  # malformado não melhora com nova tentativa
                        continue
                    try:
                        await _tratar(conexoes[tp], env)
                        ultimo_ok = msg.offset
                    except Exception:
                        # Falha do banco: não confirma; volta a esta mensagem com conexão nova.
                        log.exception("falha no offset %s; tentando de novo", msg.offset)
                        consumidor.seek(tp, msg.offset)
                        try:
                            await conexoes.pop(tp).close()
                        finally:
                            await asyncio.sleep(1)
                        break
                return tp, ultimo_ok

            feitos = await asyncio.gather(*(particao(tp, msgs) for tp, msgs in lotes.items()))
            confirmar = {tp: ultimo + 1 for tp, ultimo in feitos if ultimo is not None}
            if confirmar:
                await consumidor.commit(confirmar)
    finally:
        await consumidor.stop()
        for c in conexoes.values():
            await c.close()


async def publicar(produtor: AIOKafkaProducer) -> None:
    conn = await psycopg.AsyncConnection.connect(BANCO, autocommit=True)
    while True:
        try:
            async with conn.transaction():
                cur = await conn.execute(
                    "SELECT id_evento, id_conversa, payload FROM respostas "
                    "WHERE NOT publicada AND publicar_em <= now() ORDER BY publicar_em LIMIT 100 "
                    "FOR UPDATE SKIP LOCKED"
                )
                linhas = await cur.fetchall()
                # Envia o lote todo e espera os acks juntos (antes era um ack por vez). O produtor
                # idempotente mantém a ordem de envio dentro da partição, logo dentro da conversa.
                vezes = 2 if estado["modo"] == "duplicar" else 1
                acks = []
                for _id_evento, id_conversa, payload in linhas:
                    valor = json.dumps(payload).encode()
                    for _ in range(vezes):
                        acks.append(await produtor.send(VOLTA, value=valor, key=str(id_conversa).encode()))
                await asyncio.gather(*acks)
                if linhas:
                    await conn.execute("UPDATE respostas SET publicada = true WHERE id_evento = ANY(%s)",
                                       ([x[0] for x in linhas],))
            if not linhas:
                await asyncio.sleep(0.1)
        except Exception:
            log.exception("publicação")
            await asyncio.sleep(1)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    async with await psycopg.AsyncConnection.connect(BANCO, autocommit=True) as conn:
        await conn.execute(ESQUEMA)
    produtor = AIOKafkaProducer(bootstrap_servers=KAFKA, acks="all", enable_idempotence=True)
    await produtor.start()
    tarefas = [asyncio.create_task(consumir()), asyncio.create_task(publicar(produtor))]
    yield
    for t in tarefas:
        t.cancel()
    await produtor.stop()


app = FastAPI(title="Agente mock", lifespan=ciclo_de_vida)


class Modo(BaseModel):
    modo: Literal["normal", "lento", "duplicar", "fora"]


@app.post("/modo")
async def mudar_modo(m: Modo):
    estado["modo"] = m.modo
    log.info("modo = %s", m.modo)
    return estado


@app.get("/saude")
async def saude():
    return {"ok": True, **estado}
