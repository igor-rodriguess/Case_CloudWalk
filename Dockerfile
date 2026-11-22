# Uma imagem para os serviços Python (núcleo, broker, agente mock, simulador de canais);
# cada serviço do compose escolhe o comando.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations migrations
COPY contrato contrato
COPY nucleo nucleo
COPY broker broker
COPY agente_mock agente_mock
COPY canais canais
