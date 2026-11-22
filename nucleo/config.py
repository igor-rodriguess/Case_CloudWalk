"""Configuração do núcleo por variáveis de ambiente (docs/implementacao.md, seção 10)."""

import os


def _bool(nome: str, padrao: bool = True) -> bool:
    return os.getenv(nome, str(padrao)).strip().lower() in ("1", "true", "sim", "yes")


def _int(nome: str, padrao: int) -> int:
    return int(os.getenv(nome, padrao))


def _float(nome: str, padrao: float) -> float:
    return float(os.getenv(nome, padrao))


DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://helpdesk:helpdesk@localhost:5433/helpdesk"
)
BROKER_URL = os.getenv("BROKER_URL", "http://localhost:8100")
CANAIS_URL = os.getenv("CANAIS_URL", "http://localhost:8300")

# Chaves de ablação do experimento.
OUTBOX_ATIVA = _bool("OUTBOX_ATIVA")
INBOX_ATIVA = _bool("INBOX_ATIVA")
FENCING_ATIVO = _bool("FENCING_ATIVO")
TIMEOUT_ATIVO = _bool("TIMEOUT_ATIVO")

TIMEOUT_AGENTE_S = _int("TIMEOUT_AGENTE_S", 30)
RETENTATIVAS_MAX = _int("RETENTATIVAS_MAX", 8)
BACKOFF_BASE_S = _float("BACKOFF_BASE_S", 0.5)
BACKOFF_TETO_S = _float("BACKOFF_TETO_S", 60)
RELAY_INTERVALO_MS = _int("RELAY_INTERVALO_MS", 100)
RELAY_RESERVA_S = _int("RELAY_RESERVA_S", 30)
RELAY_WORKERS = _int("RELAY_WORKERS", 8)
REQUISICAO_TIMEOUT_S = _float("REQUISICAO_TIMEOUT_S", 5)
AGENDADOR_INTERVALO_MS = _int("AGENDADOR_INTERVALO_MS", 500)
DISTRIBUIDOR_INTERVALO_S = _float("DISTRIBUIDOR_INTERVALO_S", 1)
ENVELHECIMENTO_S = _int("ENVELHECIMENTO_S", 600)
HISTORICO_N = _int("HISTORICO_N", 20)
PERFIL_JANELA_DIAS = _int("PERFIL_JANELA_DIAS", 30)
CAPACIDADE_HUMANO = _int("CAPACIDADE_HUMANO", 3)
CAPACIDADE_IA = _int("CAPACIDADE_IA", 1_000_000)  # sem limite na entrega; limite por custo é Evolução
PRAZO_RESPOSTA_S = _int("PRAZO_RESPOSTA_S", 120)
OUTBOX_LIMITE_S = _int("OUTBOX_LIMITE_S", 60)
WORKERS_ATIVOS = _bool("WORKERS_ATIVOS")
DB_POOL = _int("DB_POOL", 10)  # por processo; API com 4 processos + trabalhador cabem nas 100 conexões


def chaves() -> dict:
    return {
        "OUTBOX_ATIVA": OUTBOX_ATIVA,
        "INBOX_ATIVA": INBOX_ATIVA,
        "FENCING_ATIVO": FENCING_ATIVO,
        "TIMEOUT_ATIVO": TIMEOUT_ATIVO,
        "TIMEOUT_AGENTE_S": TIMEOUT_AGENTE_S,
        "RETENTATIVAS_MAX": RETENTATIVAS_MAX,
    }
