"""Broker: a ponte da estrutura atual da CloudWalk (webhook -> Kafka -> agente e volta).

Duas regras (docs/arquitetura.md 11.4):
- só responde 200 ao webhook depois do ack do Kafka (acks=all, produtor idempotente);
- só confirma o offset da volta depois de o núcleo responder 2xx. Núcleo fora (503 ou
  conexão recusada) = pausa a partição e tenta de novo, sem limite: contrapressão, não perda.
Sem banco e sem inbox; é o único produtor no Kafka.
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

import httpx
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from contrato import Envelope

KAFKA = os.getenv("KAFKA_BOOTSTRAP", "localhost:19092")
NUCLEO_URL = os.getenv("NUCLEO_URL", "http://localhost:8000")
RETENTATIVAS_MAX = int(os.getenv("RETENTATIVAS_MAX", 8))
IDA, VOLTA, ERROS = "helpdesk.para-agente", "agente.para-helpdesk", "helpdesk.erros"

logging.basicConfig(level=logging.INFO, format='{"servico":"broker","nivel":"%(levelname)s","msg":"%(message)s"}')
log = logging.getLogger("broker")
estado = {"produtor": None}


async def _para_erros(produtor, chave: bytes | None, valor: bytes, motivo: str) -> None:
    await produtor.send_and_wait(ERROS, value=valor, key=chave, headers=[("motivo", motivo.encode())])
    log.warning("evento para helpdesk.erros: %s", motivo)


async def volta(produtor: AIOKafkaProducer) -> None:
    consumidor = AIOKafkaConsumer(
        VOLTA, bootstrap_servers=KAFKA, group_id="broker-volta", enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    await consumidor.start()
    http = httpx.AsyncClient(timeout=10)
    falhas_500: dict[tuple, int] = {}
    pausadas: dict[TopicPartition, float] = {}
    try:
        while True:
            agora = asyncio.get_running_loop().time()
            for tp, ate in list(pausadas.items()):
                if agora >= ate:
                    consumidor.resume(tp)
                    pausadas.pop(tp)
            lotes = await consumidor.getmany(timeout_ms=500, max_records=500)

            async def particao(tp, mensagens):
                # Partições em paralelo; dentro de cada uma, uma mensagem por vez (ordem da conversa).
                for msg in mensagens:
                    try:  # o esquema é conferido pelo núcleo, que tolera tipo novo da 1.x
                        corpo = json.loads(msg.value)
                    except ValueError as e:
                        await _para_erros(produtor, msg.key, msg.value, f"json inválido: {str(e)[:200]}")
                        await consumidor.commit({tp: msg.offset + 1})
                        continue
                    try:
                        r = await http.post(f"{NUCLEO_URL}/agente/eventos", json=corpo)
                        status = r.status_code
                    except httpx.HTTPError:
                        status = 503
                    if status < 300:
                        await consumidor.commit({tp: msg.offset + 1})
                        falhas_500.pop((tp, msg.offset), None)
                        continue
                    if 400 <= status < 500:
                        await _para_erros(produtor, msg.key, msg.value, f"núcleo respondeu {status}")
                        await consumidor.commit({tp: msg.offset + 1})
                        continue
                    if status == 500:
                        n = falhas_500.get((tp, msg.offset), 0) + 1
                        falhas_500[(tp, msg.offset)] = n
                        if n >= RETENTATIVAS_MAX:
                            await _para_erros(produtor, msg.key, msg.value, "núcleo 500 repetido")
                            await consumidor.commit({tp: msg.offset + 1})
                            continue
                    # 503 ou rede: volta para esta mensagem e pausa a partição por um tempo.
                    consumidor.seek(tp, msg.offset)
                    consumidor.pause(tp)
                    pausadas[tp] = agora + min(30, 0.5 * 2 ** min(falhas_500.get((tp, msg.offset), 1), 6))
                    return

            await asyncio.gather(*(particao(tp, msgs) for tp, msgs in lotes.items()))
    finally:
        await consumidor.stop()
        await http.aclose()


async def supervisionar(produtor: AIOKafkaProducer) -> None:
    """Reinicia o caminho de volta se ele cair. O consumidor recomeça do último offset
    confirmado: nada se perde, no máximo reentrega (a inbox do núcleo absorve)."""
    while True:
        try:
            estado["volta_ativa"] = True
            await volta(produtor)
        except asyncio.CancelledError:
            raise
        except Exception:
            estado["volta_ativa"] = False
            log.exception("caminho de volta caiu; reiniciando em 2 s")
            await asyncio.sleep(2)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    produtor = AIOKafkaProducer(bootstrap_servers=KAFKA, acks="all", enable_idempotence=True)
    await produtor.start()
    estado["produtor"] = produtor
    tarefa = asyncio.create_task(supervisionar(produtor))
    yield
    tarefa.cancel()
    await produtor.stop()


app = FastAPI(title="Broker (webhook e Kafka)", lifespan=ciclo_de_vida)


@app.post("/webhook")
async def webhook(request: Request):
    corpo = await request.json()
    try:
        env = Envelope.model_validate(corpo)
    except ValidationError as e:
        return JSONResponse(status_code=422, content={"erro": e.errors(include_url=False)})
    try:
        await estado["produtor"].send_and_wait(
            IDA, value=json.dumps(corpo).encode(), key=str(env.id_conversa).encode()
        )
    except Exception as e:
        log.warning("kafka indisponível: %s", e)
        return JSONResponse(status_code=503, content={"erro": "kafka indisponível"})
    return {"ok": True}


@app.get("/saude")
async def saude():
    if not estado.get("volta_ativa", True):
        return JSONResponse(status_code=503, content={"ok": False, "volta": "reiniciando"})
    return {"ok": True}
