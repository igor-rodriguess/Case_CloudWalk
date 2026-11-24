# Testes de carga completos

Complementam o experimento por ablação (README, "Resultados"). O experimento mede se cada proteção evita a falha dela a 50 msg/s; estes testes medem **quanto o sistema aguenta**, **se aguenta rajadas grandes sem perder nem duplicar** e **se as telas do front aguentam ser consultadas** enquanto isso. Tudo numa máquina só (limitação declarada).

Critérios escritos em 2026-11-23, **antes de rodar**. Resultados no fim deste arquivo; dados brutos em `resultados/carga/`.

## Testes

| Teste | Como | O que mede |
|---|---|---|
| T1 Rampa | Degraus de 40, 60, 80, 100, 120 e 140 msg/s no total (metade do cliente, metade do agente), 150 s cada, sem pausa. Conversas curtas (6 mensagens a cada 10 s) para chegar ao regime dentro do degrau. Mede os últimos 100 s de cada degrau | Ponto de ruptura: o maior degrau sem recusa, sem perda, sem duplicata e com p95 interna < 500 ms |
| T2 Rajada | 20.000 mensagens de 5.000 clientes enviadas o mais rápido possível (150 requisições em voo) | Vazão máxima da entrada; se, depois de drenar, todas as mensagens têm resposta, sem perda nem duplicata |
| T3 Leitura do front | 100 clientes consultando por 60 s as telas que o front relê a cada 2 s (`/painel/fila`, `/conversas`, `/supervisor/metricas`, `/filas/ativa`) com 50 msg/s de fundo | Latência das telas sob carga |
| Reconciliação | `GET /supervisor/reconciliacao` no fim de tudo | Invariantes I1 a I6 zeradas |

### Achado de método: o gerador tem de rodar dentro da rede do Docker

Antes da bateria, a miniatura da rajada aceitou só ~12 msg/s. A bancada (`carga/bancada.py`) separou a causa:

| Teste (10 requisições simultâneas) | Do Windows (`localhost`) | De dentro da rede do compose |
|---|---|---|
| `GET /saude` (não faz nada) | ~25 req/s | 207 req/s |
| `POST /mensagens` | 22 msg/s | 92 msg/s |

O limite de ~20 req/s é do encaminhamento de porta do Docker Desktop no Windows, não do sistema; com 150 simultâneas ele chega a derrubar conexões. Consequências:
- estes testes rodam de dentro da rede do compose (`docker compose run ... nucleo`, com `CARGA_DENTRO_DOCKER=1`);
- **a saturação "perto de 70 msg/s" usada para escolher 50 msg/s no experimento foi medida pelo Windows e mistura o limite do instrumento com o do sistema.** O experimento continua válido para o que mede (com e sem cada proteção, mesma carga, mesmo caminho), mas o limite de capacidade sai deste arquivo, não dele;
- dentro do Docker, até o `/saude` leva ~47 ms por requisição isolada, constante até 10 simultâneas: assinatura do atraso de 40 ms do ACK atrasado do TCP entre cliente e servidor HTTP. Afeta latência por salto, não vazão com concorrência. Não investigado a fundo.

Comando (ambiente no ar, banco limpo):

```bash
docker compose run --rm --no-deps -v "${PWD}/carga:/app/carga" -v "${PWD}/resultados:/app/resultados" \
  -e CARGA_DENTRO_DOCKER=1 -e CARGA_NUCLEO=http://nucleo:8000 -e CARGA_MOCK=http://agente_mock:8200 \
  -e CARGA_EM_VOO=50 -e JUIZ_NUCLEO_DB=postgresql://helpdesk:helpdesk@postgres:5432/helpdesk \
  -e JUIZ_CANAIS_DB=postgresql://helpdesk:helpdesk@postgres:5432/canais \
  --entrypoint python nucleo -u -m carga.completo
```

A CPU por contêiner é amostrada pelo host a cada ~8 s em `resultados/carga/docker-stats.csv`.

## Critérios para avançar

| Critério | Passa se |
|---|---|
| C1 Capacidade | A rampa sustenta **pelo menos 50 msg/s** (a carga do experimento) com zero recusa, zero perda, zero duplicata e p95 interna < 500 ms |
| C2 Rajada | As 20.000 mensagens entram (zero 5xx) e, depois da drenagem, **nenhuma conversa sem resposta e zero duplicata**. A perda é contada por conversa (a última mensagem de cada cliente tem resposta ou escala), porque mensagens quase simultâneas do mesmo cliente podem ser respondidas juntas pelo agente, que recebe o histórico; a contagem por mensagem fica registrada como informação |
| C3 Front | p95 de cada tela < 1 s e zero erro, com 100 clientes e carga de fundo |
| C4 Integridade | Reconciliação com **zero** em I1 a I6 depois dos três testes |

Os quatro passando: o backend está pronto para a próxima fase (front e demonstração). C1 abaixo de 100 msg/s não reprova: confirma a limitação já declarada de que a meta de 100 msg/s fica sem evidência nesta máquina.

## Resultados

RESULTADOS_CARGA
