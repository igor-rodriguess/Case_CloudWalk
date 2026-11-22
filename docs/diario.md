# Diário de desenvolvimento

Uma entrada por parte construída. A última entrada diz onde paramos.

---

## Fatia 1, passo 1: infraestrutura, banco e tópicos

**Data:** 2026-11-17 a 2026-11-19 · **Commit:** `b5af437` · Feito antes do ritual; registrado depois.

**O que existe**

| Arquivo | Papel |
|---|---|
| `docker-compose.yml` | Sobe `postgres` (porta 5433 no host) e `redpanda` (19092). `topicos` e `migracoes` rodam uma vez e terminam |
| `infra/postgres/01-agente-mock.sql` | Cria o banco `agente_mock` na primeira subida do volume |
| `nucleo/infra/modelos.py` | Tabelas `clientes`, `conversas`, `mensagens` em SQLAlchemy 2.0 |
| `migrations/versions/0001_fatia1_tabelas.py` | Migration que cria as três tabelas |
| `alembic.ini`, `migrations/env.py` | Configuração do Alembic; a URL vem de `DATABASE_URL` |
| `nucleo/Dockerfile`, `nucleo/requirements.txt` | Imagem usada pelo serviço `migracoes` |

**Decisões**
- Portas do host 5433 e 19092 para não colidir com outros projetos.
- psycopg 3 como único driver (síncrono no Alembic, assíncrono na API).
- Colunas `id_atribuicao`, `causado_por` e `seq_outbox` já existem, nulas: o contrato não muda depois.
- Sem índice único de conversa aberta: esta é a versão ingênua do experimento. Entra na fatia 2.
- Convenção de nomes nas constraints, para a migration sair igual em qualquer máquina.

**Problema encontrado**
- O nome da check constraint saiu duplicado (`ck_mensagens_ck_mensagens_autor_tipo`), porque a convenção aplicou o prefixo sobre um nome que já tinha prefixo. Corrigido com `op.f()`, que marca o nome como final.

**Como verificar**

```bash
docker compose up -d --build
docker compose ps -a
docker compose exec postgres psql -U helpdesk -d helpdesk -c "\dt"
docker compose exec redpanda rpk topic list
```

Esperado: `postgres` e `redpanda` healthy; `topicos` e `migracoes` com `Exited (0)`; quatro tabelas (as três mais `alembic_version`); três tópicos.

**Perguntas de banca**
1. Por que a migration é escrita à parte dos modelos, se os dois descrevem as mesmas tabelas?
2. Por que `topicos` e `migracoes` são serviços que terminam, e não parte do núcleo?
3. Por que as colunas de atribuição já existem na fatia 1 se ninguém as usa?
