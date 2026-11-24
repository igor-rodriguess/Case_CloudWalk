# Testes de carga completos

Complementam o experimento por ablação (README, "Resultados"). O experimento mede se cada proteção evita a falha dela a 50 msg/s; estes testes medem **quanto o sistema aguenta**, **se aguenta rajadas grandes sem perder nem duplicar** e **se as telas do front aguentam ser consultadas** enquanto isso. Tudo numa máquina só (limitação declarada).

Critérios escritos em 2026-11-23, **antes de rodar**. Resultados no fim deste arquivo; dados brutos em `resultados/carga/`.

## Testes

| Teste | Como | O que mede |
|---|---|---|
| T1 Rampa | Degraus de 40, 60, 80, 100, 120, 140, 160 e 200 msg/s no total (metade do cliente, metade do agente), 150 s cada, sem pausa. Conversas curtas (6 mensagens a cada 10 s) para chegar ao regime dentro do degrau. Mede os últimos 100 s de cada degrau | Ponto de ruptura: o maior degrau sem recusa, sem perda, sem duplicata e com p95 interna < 500 ms |
| T2 Rajada | 20.000 mensagens de 5.000 clientes enviadas o mais rápido possível (50 requisições em voo, `CARGA_EM_VOO`) | Vazão máxima da entrada; se, depois de drenar, todas as mensagens têm resposta, sem perda nem duplicata |
| T3 Leitura do front | 100 clientes consultando por 60 s as telas que o front relê a cada 2 s (`/painel/fila`, `/conversas`, `/supervisor/metricas`, `/filas/ativa`) com 50 msg/s de fundo | Latência das telas sob carga |
| T4 Volume | 100.000 mensagens de 20.000 clientes (5 cada), o mais rápido possível, depois dos outros testes. Pedido do usuário em 23/11. Com as 100 mil respostas, são ~200 mil mensagens nas duas direções: ~1,7 vez o dia base inteiro (10 mil atendimentos × 12 mensagens = 120 mil/dia, arq 3) num lote só | Mesma pergunta do T2 numa escala maior: entra tudo, sem 5xx, e depois da drenagem nenhuma conversa fica sem resposta e nenhuma resposta duplica |
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
| C4 Integridade | Reconciliação com **zero** em I1 a I6 depois dos testes |
| C5 Volume | Os mesmos critérios do C2 para as 100.000 mensagens do T4 |

Os quatro passando: o backend está pronto para a próxima fase (front e demonstração). C1 abaixo de 100 msg/s não reprova: confirma a limitação já declarada de que a meta de 100 msg/s fica sem evidência nesta máquina.

## Resultados

Duas baterias em 23/11/2026, mesma máquina (14 núcleos lógicos, tudo no Docker Desktop), gerador dentro da rede do compose:

- **antes** (`resultados/carga/antes/`): código até `1bffbfe`;
- **depois** (`resultados/carga/`): com as quatro correções que a primeira bateria motivou:
  - `4e5f806`: linha da IA sem trava;
  - `8fa2f7f`: distribuidor com 4 tarefas e índice parcial da fila;
  - `bb644e9`: trabalhador em 2 processos;
  - `9c95950`: canal deduplica pelo id do evento.

O T2 não foi repetido: o T4 é o mesmo teste com 5 vezes o volume e os mesmos critérios.

### T1 Rampa

"Sem resposta" conta por mensagem; nas duas baterias nenhuma conversa ficou sem resposta.

| msg/s totais | Sem resposta (antes) | Sem resposta (depois) | p95 interna (antes) | p95 interna (depois) | Espera p95 da 1ª resposta (antes) | Espera p95 da 1ª resposta (depois) |
|---|---|---|---|---|---|---|
| 40 | 0 | 0 | 0,26 s | 0,15 s | 2,2 s | 1,9 s |
| 60 | 0 | 0 | 0,54 s | 0,54 s | 2,4 s | 3,0 s |
| 80 | 394 | 0 | 27 s | 22 s | 53 s | 43 s |
| 100 | 1.088 | 0 | 30 s | 31 s | 65 s | 62 s |
| 120 | 1.960 | 0 | 18 s | 71 s | 43 s | 159 s |
| 140 | 4.319 | 0 | 4,6 s | 129 s | 21 s | 302 s |
| 160 | 4.605 | 0 | 5,0 s | 189 s | 28 s | 400 s |
| 200 | 6.802 | 0 | 1,9 s | 218 s | 32 s | 421 s |

Nos dois códigos:
- nenhuma recusa e nenhuma duplicata em degrau nenhum;
- a entrada aceitou toda a oferta.

**Leitura.** O joelho fica entre 60 e 80 msg/s totais nos dois códigos. A diferença está no que acontece depois do joelho.

- **Antes**, o distribuidor (~5 conversas novas/s) era o gargalo:
  - as conversas esperavam na fila e as mensagens se acumulavam;
  - o agente respondia várias de uma vez, porque recebe o histórico;
  - por isso a p95 "melhorava" nos degraus altos: o sistema fazia menos trabalho por mensagem.
- **Depois**, cada mensagem recebe a própria resposta:
  - zero mensagens sem resposta própria em todos os degraus;
  - o excesso vira fila explícita (Lei de Little): a espera cresce com o degrau e drena depois (337 s de drenagem).
- O novo limite é a CPU, medida por `docker stats` nos degraus de 80 a 200:
  - Postgres ~2,8 núcleos;
  - API ~2,5 núcleos;
  - cada processo do trabalhador perto de 1 núcleo (Python, um laço por processo);
  - o próprio gerador ~1 núcleo.

### T3 Leitura do front

| Tela | p95 (antes) | p95 (depois) | p99 (depois) | Erros (depois) | Sem carga (depois, mín.–máx. de 5) |
|---|---|---|---|---|---|
| `/painel/fila` | 4,7 s | 4,1 s | 6,2 s | 0 | 10–42 ms |
| `/conversas?estado=com_ia` | 5,2 s | 3,9 s | 6,3 s | 1 de 1.185 | 24–75 ms |
| `/supervisor/metricas` | 4,7 s | 4,2 s | 6,7 s | 0 | 68–115 ms |
| `/filas/ativa` | 4,6 s | 3,6 s | 6,1 s | 0 | 4–6 ms |

As telas atenderam 79 leituras/s no total (4.740 em 60 s), contra 50 msg/s de escrita de fundo. Sem carga, cada tela responde em menos de 120 ms. Portanto o custo não é da consulta: é fila nos 4 processos da API, disputados com as escritas.

### T4 Volume (100 mil mensagens)

| Medida | Valor |
|---|---|
| Mensagens aceitas | 100.000 de 100.000 (todas HTTP 200, nenhuma recusa) |
| Vazão de entrada | 52,9 msg/s do cliente (envio em 31,5 min); POST p50 0,68 s, p95 2,5 s |
| Conversas sem resposta | **0 de 20.000** |
| Respostas duplicadas | **0**; o canal absorveu 0 reenvios (`GET /duplicatas`) |
| Mensagens sem resposta própria | 1.581 (1,6%): respondidas junto com a seguinte do mesmo cliente; I1 = 0 confirma que toda mensagem teve desfecho |
| Última resposta | 40,9 min depois do início (drenagem de 9,4 min) |
| Espera p95 da resposta | 12 min: a entrada (~53/s) passou da vazão de ponta a ponta (~41/s) e o excesso esperou na fila |

Antes (T2, 20 mil mensagens): 0 conversas sem resposta, mas **1 resposta duplicada**. O relay pausou por CPU além da reserva de 30 s e reentregou um item. A correção deixou o adaptador do canal deduplicar pelo id do evento: entrega pelo menos uma vez, com deduplicação na ponta.

### Reconciliação

I1, I1b e I2 a I6 com **zero** depois de cada bateria.

### Veredito

| Critério | Resultado |
|---|---|
| C1 Capacidade | **Não passa, por pouco.** O degrau de 40 msg/s passa (p95 interna 0,15 s). O de 60 passa em perda, duplicata e recusa, mas a p95 interna dá 0,54 s, 39 ms acima do limite de 500 ms (igual no código antigo). Não houve degrau de 50; o E1 a 50 msg/s, com conversas longas, deu p95 interna de 0,10 s. Capacidade sustentada nesta máquina: entre 60 e 80 msg/s totais. A meta de 100 msg/s continua sem evidência, como já declarado |
| C2 Rajada | **Não passou no código antigo** (1 duplicata em 20 mil). Coberto pelo C5 no código novo |
| C3 Front | **Não passa.** p95 de 3,6 a 4,2 s sob 100 clientes e 50 msg/s de fundo (meta < 1 s); 1 erro em 4.740. Sem carga, < 120 ms |
| C4 Integridade | **Passa.** Zero em todas as invariantes |
| C5 Volume | **Passa.** 100 mil aceitas, 0 conversas sem resposta, 0 duplicatas |

**Pode avançar?** Sim para o front e a demonstração, com duas limitações declaradas.

- O que o case pede de difícil se sustentou com 5 vezes o volume do T2: não perder nem duplicar, com estado correto (C4, C5).
- O volume real cabe com folga. O dia base inteiro (120 mil mensagens) passaria em ~50 min a 41 msg/s. Pelas premissas da arq 3, o pico base (até ~14 msg/s com concentração em horário comercial) e o pico de estresse de 5x (~35 msg/s) ficam abaixo do joelho. O pico de estresse concentrado (~70 msg/s, premissa) cai dentro do joelho.
- As duas limitações:
  - **Capacidade.** Entre 60 e 80 msg/s totais numa máquina só. Acima disso o sistema não perde nada, mas a espera cresce sem limite: não há controle de admissão (Evolução). Escalar pede mais processos de trabalhador e da API, o que é seguro porque todo trabalho é reservado com `SKIP LOCKED`, mas não foi testado em mais de uma máquina.
  - **Telas sob carga pesada.** 100 painéis abertos ao mesmo tempo, com o sistema já a 50 msg/s, passam de 1 s. A demo usa poucos. Caminhos prováveis, nenhum medido: cache curto (1–2 s) nas métricas e na fila, ou uma réplica de leitura.
