FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY nucleo/requirements.txt nucleo/requirements.txt
RUN pip install --no-cache-dir -r nucleo/requirements.txt

COPY alembic.ini .
COPY migrations migrations
COPY nucleo nucleo
