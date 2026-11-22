# Revisão da arquitetura, rodada 3 (validador)

Data: 2026-11-21. Lido: `CLAUDE.md`, `docs/arquitetura.md` (arq, 697 linhas), `docs/implementacao.md` (impl, 820), `docs/referencias.md`, `docs/diferenciais.md`, as revisões das rodadas 1 e 2 e o código da fatia 1 (`docker-compose.yml`, `nucleo/infra/modelos.py`, migration 0001, `contrato/envelope.py`). Nenhum arquivo existente foi alterado.

Régua combinada: 10 = tudo o que é corrigível no desenho e no plano está corrigido, e o que não é corrigível está declarado com o efeito. Limite do enunciado ou do ambiente declarado não tira ponto; escondido ou ausente, tira. Não contam como erro novo: `envelope.py` aceita só `"1.0"` e não tem `agente.processando`; README; imagem do compose.

---

## 1. Itens da rodada 2

| # | Status | Onde se prova (e ressalva) |
|---|---|---|
| R1 | parcial | Prazo desde o ack: arq 11.5, impl 7.3 passo 1, 7.4, 13.2; E6/E7 desligados preveem perda (impl 14). Coluna "escaladas" na tabela da parte 1. Falta: "espera até a 1ª resposta" na tabela; escala vista na ponta (o juiz ainda aceita escala gravada no banco, arq 17, impl 14) |
| R2 | resolvido | arq 11.1; impl 5.1 (índice sem unicidade), 5.2, 7.2 (chave `entrada:canal:id_externo`), 13.1 com a chave desligada |
| R3 | resolvido no desenho | arq 11.9, 12 (JSON e `ao_abrir_disjuntor`), 17 (H2 por política); impl 7.9, 8 (validação), 13.3, 14 (E8). A política `reter` não tem quem a execute (N2) |
| R4 | resolvido | impl 8: uma conversa por transação, `:filas` só com grupo livre, prioridade inteira, teste de fome em 13.3. Resíduo: envelhecimento pela idade da conversa e decisão 10 pendente (N3) |
| R5 | resolvido | impl 7.1 (capacidade antes de `encerrar_atribuicao`), 13.2 (devolução com a IA no limite); arq 11.2 passo 4. Efeito colateral no texto da ordem de travas (N8) |
| R6 | resolvido | arq 11.3, 11.5; impl 7.3 (parágrafo depois de `atraso`), 13.2. O teste "nenhuma por timeout" ficou falso por outro motivo (N4) |
| R7 | não resolvido | impl 12, fatia 1: "publicação direta"; contradiz arq 9 ("Único que fala com o Kafka") e impl 3 |
| R8 | não resolvido | impl 14: perdida por mensagem, sem cobertura por `seq` |
| R9 | parcial | arq 11.9 e impl 7.9 dizem que as conversas com a IA seguem escalando, sem o número; a parte 2 não tem previsão (N7) |
| R10 | não resolvido | impl 10 (`CAPACIDADE_HUMANO = 3`, e-mail 72 h); nada declarado |
| R11 | não resolvido | impl 14, E7: uma morte por execução |
| R12 | parcial | Roteiro e gravação de reserva em arq 19.2. Faltam: definição de "Recuperação", CSV bruto, script das tabelas, sementes do jitter e do mock |
| R13 | não resolvido | impl 14, E2: "Previsto desligada: Zero; p95 maior" |
| R14 | não resolvido | impl 7.5 passo 5, sem declaração |
| R15 | não resolvido, agravado | impl 7.1 (capacidade da IA conta outbox pendente), 12 (fatia 2 semeia a IA sem distribuidor). Ver N1 |
| R16 | resolvido | impl 7.6 (`MOCK_TROCAS = 6`), 14 (fim pelo mock; texto sem gatilho) |
| R17 | não resolvido | impl 14, E4 com duas chaves sem matriz; arq 8 omite o cliente em `com_ia → escalada` |
| R18 | parcial | arq 19.1 replaneja com a velocidade medida e define cortes A a D, mas é Proposta (valem os marcos antigos, já perdidos); estimativa da fatia 2 sem base na velocidade; janela final sobrecarregada (seção 4, itens 19 a 22) |
| R19 | não resolvido | impl 7.3 ("podem ir em paralelo", sem número), 7.5, 11 (sem latência da volta) |
| R20 | resolvido | impl 14: 8,3 conversas/s, 6 mensagens a cada 84 s, L ≈ 3.500, aquecimento de 7 min; arq 3 |

**Contagem (20 itens):** 7 resolvidos (R2, R3, R4, R5, R6, R16, R20), 4 parciais (R1, R9, R12, R18), 9 não resolvidos (R7, R8, R10, R11, R13, R14, R15, R17, R19).

---

## 2. Regressões e contradições novas

| # | Sev. | Onde | Problema |
|---|---|---|---|
| N1 | alta | impl 7.1 ("timeout_agente pendentes mais eventos ainda não enviados na outbox"), 10 (`CAPACIDADE_IA = 2000`), 8 ("a fatia 2 semeia um atendente IA"); arq 11.5 | **A capacidade da IA cobra dela o atraso da plataforma, e isso derruba H1 no E6 ligado.** Com o broker fora, a outbox acumula ~58 eventos/s para o broker (50 `mensagem.recebida` + 8,3 `conversa.atribuida`): a IA "lota" em ~34 s. Na parte 1 (fatias 2 a 4) não há distribuidor: a conversa nova que leva `SEM_CAPACIDADE` fica em `na_fila` sem ninguém para repescá-la, sem resposta e sem escala, e o juiz a conta como perdida **na posição ligada**. Na parte 2, a mesma conta transborda para humanos por causa de uma queda do broker. Contradiz a regra da 11.5 ("evento parado na outbox não cobra o agente"). Absorve o R15 |
| N2 | alta | impl 8 (`:filas` = filas "com algum grupo elegível ... que tem atendente livre") × impl 7.9 e arq 11.9 (`reter`: "recebe uma mensagem de espera e um `espera_retida`") | **Ninguém executa o `reter`.** Com o disjuntor aberto, a fila AI first em `reter` não tem grupo elegível, sai de `:filas`, e o distribuidor nunca olha as conversas dela: não há mensagem de espera nem `espera_retida`, e a garantia "ninguém espera além de `ESPERA_MAX_RETIDA_S`" não vale. Quebra o lado `reter` de H2 e o trecho 4:00 do roteiro (19.2). Falta também cancelar o `espera_retida` ao sair de `na_fila` (sem atribuição, ele não cai no cancelamento de 6) |
| N3 | média | impl 8 (SQL: `now() - c.criada_em`; desempate `c.criada_em`), 5.2 (índice com `criada_em`); arq 12 × 20 (decisão 10 = Evolução) × 21 | Envelhecimento e desempate usam a idade da conversa, não a espera na fila: com `ENVELHECIMENTO_S` = 600, a conversa escalada depois de 20 min com a IA já entra na fila de escalas dois degraus acima, e a reaberta depois de 23 h entra 138 degraus acima de tudo. E o SQL implementa o que a seção 20 e a 21 dizem estar fora do mês ("Pendente" na arq 12 e impl 10) |
| N4 | média | impl 14 (E6 ligado: "escaladas só por esgotamento do relay"), 13.2 ("Broker fora por 3 min: ... nenhuma por timeout") | As respostas que já estavam no caminho de volta quando o broker cai ficam presas no Kafka; os `timeout_agente` delas (nascidos no ack) vencem em 30 s e escalam, nas duas posições da chave. Ordem de grandeza: ~50 msg/s × ~1 s em voo ≈ 40 a 60 conversas (hipótese). A limitação está declarada (arq 11.5), mas a previsão e o teste a contradizem |
| N5 | média | arq 17, impl 14 (juiz) | Juiz incompleto: (a) no E7 o núcleo fica fora mais que o reenvio único do k6; a mensagem recusada na entrada nunca entrou no sistema e conta como perdida nas duas posições, contra "ligada: zero"; (b) mensagem enviada a conversa já escalada (parte 1 sem humanos; E6 por N4) não tem regra; (c) escala aceita pelo banco, não pela ponta (resíduo do R1); (d) sem cobertura por `seq` (R8) |
| N6 | média | impl 14 (`constant-arrival-rate` de conversas, "VUs pré-alocados ≈ 3.900") | Cada VU vive a conversa inteira (420 s dormindo entre mensagens): ~3.900 VUs, cada um com o próprio runtime de JavaScript, na mesma máquina do núcleo, do Postgres e do Redpanda. Consumo não medido; o próprio texto prevê que pode não sustentar. Há modelo equivalente que não precisa disso (seção 4, item 10) |
| N7 | média | arq 17 ("tabela de previsão por cenário e posição da chave"), impl 14 parte 2, 10 (`ANALISTAS_SIMULADOS`), 12 | A parte 2 não tem tabela de previsão. "Carga humana total" não diz se é pico do estoque ou contagem de conversas. O analista simulado não tem modelo (tempo de resposta, quando encerra, se devolve), e é ele que define a carga humana de H2. O script dos analistas não está na entrega de nenhuma fatia |
| N8 | baixa | arq 11.2 e impl 7.1 ("conversa → agendamento → atendente → disjuntor") × código de `transicionar` | Depois do R5, `tem_capacidade` trava o atendente novo antes de `encerrar_atribuicao` cancelar agendamentos. Não há ciclo real (no máximo um humano por transação; agendamentos só são tocados sob a trava da conversa, salvo o heartbeat, que não pede outra trava), mas a ordem escrita não é a executada |
| N9 | média | impl 7.9 ("o agendamento nasce com `sonda = true`") × 7.3 (o `timeout_agente` agora nasce no relay) | Regressão do R1 no meio-aberto: quem consome a sonda é o distribuidor, mas o prazo nasce depois, no relay, que não sabe que é sonda. E se o relay esgotar numa sonda, não nasce agendamento: a sonda nunca decide nem devolve a vaga, e o disjuntor pode ficar em meio-aberto (o A4(c) da rodada 1 de volta) |
| N10 | baixa | arq 19 ("Não sai: fatias 1 a 4") × 19.1 (corte B tira E2, E3 e E7; corte C tira a tela de acompanhamento); arq 13, 18, 19 item 7, 20 (28), `diferenciais.md` ("marco da semana 3"); arq 17 (H2 com 2 e 10 min) × 19.1 (só 2 min no plano base) | Com o 19.1 aprovado, "marco da semana 3" passa a ser fatias 3 e 4, e o D6 reduzido ficaria liberado cedo demais. "Não sai" e os cortes se contradizem |
| N11 | baixa | arq 10 (Overeem "recomendam começar por essas duas") × `referencias.md` ("ordem das táticas por fonte secundária") | Frase de fonte secundária apresentada sem rótulo |
| N12 | média | arq 2 (requisito 4, "no formato da estrutura atual"), 10, 17 (limitações) | Limite não declarado: o formato real do contrato da CloudWalk não é público, então o contrato é proposta nossa. A lista de limitações também omite canais simulados (janela de 24 h do WhatsApp, encadeamento de e-mail), ablação de uma chave por vez (sem interações), Postgres sem réplica, autenticação fixa e sem RLS, k6 na mesma máquina e qualidade do resumo não medida, todos presentes na seção 6.2 da rodada 2 |

---

## 3. Notas

D = desenho, V = viabilidade. Cada ponto abaixo de 10 aponta para itens da seção 4.

| Critério | Rodada 1 | Rodada 2 | Rodada 3 | O que falta para 10 (itens da seção 4) |
|---|---|---|---|---|
| Aderência e coerência | 7 / 6 | 7,5 / 7 | 8 / 7 | R3 e R6 fechados. Restam fatia 1 fora da fronteira (16), decisão 10 contradita pelo SQL (3), "Não sai" × cortes e "semana 3" (18), ordem de travas (17) |
| Filas configuráveis | 6 / 6 | 7 / 6 | 7,5 / 6 | Fome de fila e prioridade resolvidas. `reter` sem executor (2), envelhecimento pela idade errada (3); fatia 5 só na semana 4 (19, 22) |
| Robustez da integração | 6 / 5 | 7 / 6,5 | 7,5 / 6,5 | R1, R5 e R6 fechados no desenho. Capacidade da IA cobra a plataforma (1), sonda perdida no relay (5), relay e volta sem dimensionamento (9), 500 na partição (14) |
| Handoff com contexto | 5 / 5 | 7 / 5,5 | 7 / 5,5 | Vaga humana presa (12), analista simulado sem modelo (11), escala invisível ao cliente (6), front só na semana 4 (21) |
| Evidência de escalabilidade | 4 / 4 | 6 / 5,5 | 6,5 / 5,5 | Modelo de carga fechado (R20). Little por salto (9), k6 com ~3.900 VUs (10), E7 que não separa as posições (8), parte 2 sem previsão (11), orçamento de execução (23) |
| Honestidade nas limitações | 7 / 8 | 7,5 / 8,5 | 8 / 8,5 | Previsões coerentes com o juiz em E3, E3b, E6 desligado e E7. Erradas ainda: E6 ligado (4), E2 (7). Faltam o formato do contrato e cinco limitações (24); Overeem sem rótulo (25) |
| Reprodutibilidade | 7 / 6 | 7 / 6,5 | 7,5 / 6,5 | Carga com semente e parâmetros. Faltam recuperação, CSV, script e sementes (13); juiz (6) |
| Demonstração | 5 / 4 | 5,5 / 5 | 7 / 6 | Roteiro com falha ao vivo e gravação de reserva. Depende do `reter` (2), da aprovação e da duração (22), do front (21) |
| **Geral** | **6,0 / 4,5** | **6,5 / 5,5** | **7,0 / 6,0** | Média das linhas: 7,4 / 6,4 |

**Por que o geral fica abaixo da média.** Desenho: as duas hipóteses principais ainda não podem sair como escritas. H1 no E6 ligado produz perda por N1 e escaladas por timeout que a previsão nega (N4); o lado `reter` de H2 não tem executor (N2) e a parte 2 não tem previsão (N7). Viabilidade: o replanejamento existe, mas é Proposta; a fatia 2 "em uma semana" não se apoia na velocidade medida (a fatia 1, bem menor, leva a semana inteira); o primeiro código de interface só aparece na semana 4 se o corte C entrar; e os dois últimos dias concentram E8, E9, README, gravação e ensaio.

**Progresso.** +0,5 / +0,5 sobre a rodada 2. Os seis altos da rodada 2 viraram quatro resolvidos (R2 a R5) e dois parciais (R1, R18). Repete-se o padrão da rodada anterior: cada correção certa encontrou outra peça (R1 → N4 e N9; R3 → N2; R4 → N3; R5 → N8). Por isso a rodada 4 precisa conferir as correções desta, e não só marcá-las.

---

## 4. Lista fechada do que falta para 10

Formato: critério afetado (D, V); correção que o redator aplica sem decidir nada; tipo. Em `decisão do usuário`, a recomendação vem primeiro e é o que o redator aplica se o usuário aprovar.

### Desenho e mecanismo

1. **Capacidade da IA sem cobrar a plataforma** (N1, R15). Robustez D/V, evidência D. Em impl 7.1 (parágrafo "Capacidade") e arq 12: "A IA conta só `timeout_agente` pendentes das atribuições dela (enviados e sem resposta); evento parado na outbox é atraso da plataforma e não conta (11.5)". Em impl 10, `CAPACIDADE_IA`: "conferida a partir da fatia 5; antes não há distribuidor que repesque `SEM_CAPACIDADE`". Em impl 7.4: "com `TIMEOUT_ATIVO = false` não há `timeout_agente` e a capacidade da IA não é conferida (efeito no E4 e no E5, declarado)". Teste novo em 13.3: broker fora 60 s não deixa a IA sem capacidade. `correção`.
2. **Executor do `reter`** (N2). Filas D, robustez D, demonstração V. Em impl 8, depois do laço de atribuição, um passo "retenção" no mesmo ciclo: para cada fila com disjuntor da IA não fechado e política `reter` (ou `transbordar` sem outro grupo), seleciona `na_fila` sem `espera_retida` pendente, com `FOR UPDATE SKIP LOCKED`, uma conversa por transação; grava a mensagem de espera (outbox, destino `canal`) e cria o `espera_retida`. Índice único parcial `agendamentos (id_conversa) WHERE tipo = 'espera_retida' AND status = 'pendente'`. Em impl 6 (Atribuição): "sair de `na_fila` cancela o `espera_retida` pendente (`motivo_fim = atribuida`)". Mesmo texto, resumido, em arq 11.9 e 12. Teste em 13.3: disjuntor aberto por 6 min; a conversa retida recebe a mensagem de espera uma vez e escala aos 300 s com `agente_indisponivel`. `correção`.
3. **Envelhecimento** (N3). Filas D, coerência D. Coluna `conversas.na_fila_desde timestamptz`, gravada por `transicionar` ao entrar em `na_fila` ou `escalada` (impl 5.1 fatia 5, 5.2, 7.1); no SQL de impl 8 e no índice parcial, `na_fila_desde` no lugar de `criada_em`. Decisão 10: **recomendação: Proposta**, porque sem ela a fila de prioridade baixa que divide equipe com uma alta pode esperar sem limite sob carga contínua, e o custo é uma expressão no `ORDER BY`; arq 20 passa a "Proposta", sai da arq 21, e somem os "Pendente" da arq 12 e da impl 10. Alternativa: tirar a expressão do SQL e declarar em arq 12 "sem envelhecimento, fila de prioridade menor que divide grupo com outra pode esperar sem limite sob carga contínua". `decisão do usuário`.
4. **Caminho de volta parado** (N4). Honestidade D, evidência D. Impl 14, E6 ligado: "Zero perda, com atraso; escaladas por esgotamento do relay e, nas duas posições, por timeout das respostas que estavam no caminho de volta quando o broker caiu (ordem de 40 a 60, hipótese: ~50 msg/s × ~1 s em voo)". Mesma ressalva no E6 desligado. Impl 13.2: "Broker fora por 3 min, começando sem mensagem em voo: ... nenhuma por timeout"; e um segundo caso com mensagens em voo, que escalam por `timeout` com o motivo gravado. `correção`.
5. **Sonda depois do R1** (N9). Robustez D. `atribuicoes.sonda boolean NOT NULL DEFAULT false` (impl 5.2, fatia 5), gravado pelo distribuidor quando consome a vaga; o relay copia para o `timeout_agente` (impl 7.3 passo 1). Esgotamento do relay numa atribuição de sonda entra em `sondas` como falha (impl 7.9: "`timeout` ou `falha_integracao` em `sondas` reabre"). Teste em 13.3: relay esgota numa sonda e o disjuntor volta a aberto. `correção`.
6. **Juiz completo** (N5, R1, R8). Evidência D, honestidade D, reprodutibilidade D. Em arq 17 e impl 14: (a) ao escalar, a plataforma manda pelo canal uma mensagem de sistema de transferência (outbox, destino `canal`, `causado_por` = evento que escalou), que o simulador grava; o juiz só conta escala por ela; (b) mensagem anterior coberta por resposta a uma posterior (`seq` menor) conta como respondida; (c) mensagem enviada a conversa já escalada vai à coluna "esperando humano", nem perdida nem respondida; (d) mensagem sem 2xx na entrada depois do reenvio vai à coluna "recusadas", fora de "perdidas"; E7 prevê recusadas nas duas posições; (e) tabela da parte 1 ganha as colunas "Recusadas", "Esperando humano" e "Espera p95 até a 1ª resposta". `correção`.
7. **Previsão do E2** (R13). Honestidade D. Impl 14: "Desligada: zero; p95 menor (sem o laço de 100 ms do relay nem as transações de reserva). Ligada: zero; p95 maior, abaixo de 500 ms. A diferença é o custo da proteção". `correção`.
8. **E7 que separa as posições** (R11). Evidência D. Impl 14, E7: "10 mortes por execução, uma a cada 60 s (`SIGKILL` e `start`)"; e a frase: "a janela entre commit e `POST` é de milissegundos; perdas esperadas com a chave desligada ≈ eventos em voo por morte × 10, ordem de unidades a dezenas (hipótese)". `correção`.
9. **Little por salto** (R19). Evidência V, robustez V. Tabela em impl 11: salto, chegada no E1 e no E2, tempo de serviço (inicial), concorrência necessária. Valores para o redator: relay ~108 itens/s no E1 e ~216 no E2, ~15 ms por item (duas transações e o `POST`) → `RELAY_WORKERS = 8` (inicial), e o laço drena até esvaziar antes de dormir `RELAY_INTERVALO_MS`; consumidor de volta do broker ~50 e ~100 eventos/s, ~10 ms por `POST` → uma tarefa por partição atribuída, ordem preservada dentro da partição; pool de conexões do núcleo ≥ workers + API. Métrica nova `latencia_volta_segundos` (evento lido do Kafka → 200 do núcleo). Impl 10 ganha `RELAY_WORKERS`. `correção`.
10. **Carga por mensagem, não por VU dormindo** (N6). Evidência V, reprodutibilidade V. Impl 14: um script (`carga/agenda.py`, com `K6_SEMENTE`) gera a agenda `(instante, id_conversa, k, id_externo, marca, canal, texto)` com as mesmas 8,3 conversas/s e 6 mensagens a cada 84 s; o k6 a reproduz com `constant-arrival-rate` de mensagens (50/s no E1); VUs ≈ chegada × latência da requisição (dezenas). L ≈ 3.500 continua no sistema; o k6 deixa de precisar de ~3.900 VUs. `correção`.
11. **Parte 2 com previsão e analista com modelo** (N7, R9). Evidência D, handoff D, honestidade D. Em impl 14: (a) tabela de previsão de E4, E4b, E5 e E8 por posição; no E8, com os números da seção 3 da rodada 2 (queda de 2 min: ~3.500 escalas que o disjuntor não evita, das conversas já com a IA; `reter` reduz a carga humana em ~20%; `transbordar`, ~0%; ordem de grandeza); (b) "carga humana total" = conversas distintas que entram em `escalada` ou em atribuição humana entre o início da queda e 10 min depois da volta; o pico do estoque vai em coluna à parte; (c) analista simulado: assume a primeira da fila dele, responde em `ANALISTA_RESPOSTA_S` (30, hipótese), encerra depois de responder a 6ª mensagem do cliente, não devolve; (d) impl 12, fatia 6, entrega também `carga/analistas.py`. Em arq 11.9: "numa queda, as ~3.500 conversas que já estão com a IA escalam por timeout; o disjuntor só protege as novas". `correção`.
12. **Vaga humana presa** (R10). Handoff D, honestidade D. **Recomendação:** declarar em arq 12 e nas limitações "conversa com humano esperando o cliente ocupa vaga até a inatividade (e-mail: até 72 h); com 3 vagas por analista, poucos e-mails sem resposta lotam a equipe"; no experimento o analista simulado encerra (item 11), então o E8 não é afetado; "vaga só quando o próximo passo é do analista" entra na arq 21. Alternativa: implementar agora a contagem por próximo passo (~meio dia). `decisão do usuário`.
13. **Resultados reproduzíveis** (R12). Reprodutibilidade D/V. Impl 14: "Recuperação = do retorno da dependência até I1 e I2 zerarem e `outbox_pendentes` voltar ao nível de antes da falha"; CSV bruto por execução em `resultados/<cenario>/<chave>/<repeticao>.csv` (registros do juiz e métricas) e `carga/tabelas.py`, que gera as tabelas do README a partir deles. Impl 10 e `.env.example`: `MOCK_SEMENTE` e `RELAY_SEMENTE` (o jitter usa `random.Random(RELAY_SEMENTE)`). `correção`.
14. **500 na partição** (R14). Robustez D. Impl 7.5 passo 5: "enquanto o 500 se repete, a partição fica parada (até ~2 min com os valores iniciais); os timeouts das conversas dela contam contra o agente. Aceito porque 500 é defeito do núcleo". `correção`.
15. **E4 em matriz e diagrama** (R17). Evidência D, coerência D. Impl 14, E4 com três células: timeout ligado e fencing desligado (mede I4); timeout e fencing ligados (zero); timeout desligado (sem troca de dono, o fencing não se aplica; mede espera). Arq 8: `com_ia --> escalada: agente escalou, cliente pediu humano, timeout ou falha de integração`. `correção`.
16. **Fatia 1 na fronteira** (R7). Coerência D, viabilidade V. **Recomendação:** fatia 1 já com broker mínimo (`POST /webhook` publica com ack; consumidor de `agente.para-helpdesk` faz `POST /agente/eventos` e confirma o offset depois do 2xx), sem pausa nem fila de erros; custa o mesmo que publicar direto, porque a publicação ainda não foi escrita, e a fatia 2 só acrescenta as regras da 11.4. Impl 12 e arq 19 item 1 ajustados. Alternativa: manter e escrever em impl 12 "temporário; contraria arq 9 até a fatia 2". `decisão do usuário`.
17. **Ordem de travas escrita** (N8). Coerência D. Arq 11.2 e impl 7.1: "conversa → atendente novo (se humano) → agendamentos → atendente antigo (se humano) → disjuntor; nunca dois humanos na mesma transação (não há `com_humano → com_humano`)". `correção`.
18. **Plano sem contradição interna** (N10). Coerência D/V. Arq 19, "Não sai": trocar "fatias 1 a 4" por "fatias 1 a 3 e a parte 1 com pelo menos E1, E3b e E6". Em arq 13, 18, 19 item 7, 20 (decisão 28) e `diferenciais.md`: "marco da semana 3" vira "fatias 1 a 6 entregues". Arq 17, H2: "quedas de 2 min; 10 min só se o bônus entrar". `correção`.

### Plano e viabilidade

19. **Fatia 2 enxuta** (R18). Viabilidade de todos os critérios. **Recomendação:** fatia 2 só com o que a parte 1 mede (migration 0002 parcial, `transicionar` sem fencing nem capacidade, outbox e relay, inbox, broker com a 11.4, chaves `OUTBOX_ATIVA` e `INBOX_ATIVA`); atribuições, fencing e `FENCING_ATIVO` vão para a fatia 3, junto do timeout, porque só a parte 2 (E4) os mede. Os testes de 13.1 se dividem entre 13.1 e 13.2. A estimativa "fatia 2 em uma semana" passa a "hipótese; recalibrar em 30/11 com a velocidade das duas fatias". `decisão do usuário`.
20. **Janela final realista** (R18). Viabilidade de evidência e demonstração. **Recomendação:** E9 sai do plano base e vira bônus (se não rodar, H3 fica declarada como não medida); o E8 de 2 min e o script dos analistas vão para o fim da semana 4; 15 e 16/12 ficam só com README, gravação de reserva e ensaio. `decisão do usuário`.
21. **Front antes da semana 4** (R18). Viabilidade de handoff e demonstração. **Recomendação:** a tela de acompanhamento da fatia 3 fica, reduzida a uma página Next.js só de leitura (estado, mensagens e auditoria de uma conversa), e sai do corte C; é o primeiro contato com o front e a base do painel da fatia 6. Sem isso, todo o Next.js nasce na semana 4. `decisão do usuário`.
22. **Aprovações pendentes** (R18, R12). Viabilidade de todos; demonstração. O usuário aprova (ou ajusta) as decisões 41 e 42, confirma a data de entrega (o texto supõe 16/12) e a duração da apresentação. Se a banca der 5 min, o redator aplica a versão curta do roteiro: corta 0:00 a 0:45 (o diagrama vira slide de 15 s) e 6:30 a 7:00 (limitações num slide final de 15 s) e reduz o trecho do broker para 1 min. `decisão do usuário`.
23. **Orçamento de execução** (R18). Evidência V. Arq 19.1, semana 3: "parte 1 = 6 cenários × 2 posições × 3 repetições ≈ 36 execuções de ~20 min (7 de aquecimento) ≈ 12 h de máquina; rodar em lote fora do horário de trabalho, por script"; se faltar tempo, 3 repetições só em E1, E3b, E6 e E7, e 1 nas demais, declarado. `correção`.

### Honestidade

24. **Limitações faltantes** (N12). Honestidade D, aderência D. Em arq 10, depois do envelope: "O formato real do contrato da CloudWalk não é público. Este contrato é proposta nossa, com base no agent bot do Chatwoot e no que o TAPI descreve (webhook, broker, Kafka); ligar o agente real exige um tradutor no broker, o único componente que fala com ele". Em arq 17, "Limitações", acrescentar com o efeito: "canais simulados: janela de 24 h do WhatsApp e encadeamento de e-mail ficam de fora; a ablação desliga uma chave por vez e não mede interações entre proteções; Postgres sem réplica: falha de disco ou de banco não é testada; autenticação por usuário fixo e isolamento por marca só por filtro com teste, sem RLS; o k6 roda na mesma máquina e disputa CPU com o sistema, então E1, E2 e E9 medem o conjunto; a qualidade do resumo de handoff não é medida (o mock escreve texto fixo); vaga humana presa por conversa à espera do cliente (item 12)". O README copia a lista. `correção`.
25. **Rótulo do Overeem** (N11). Honestidade D. Arq 10: "... que listam cinco táticas; a recomendação de começar por essas duas vem de fonte secundária (rótulo em `referencias.md`)". `correção`.

**Limites honestos já declarados e corretos (não tiram ponto):** agente mock com texto fixo (arq 17); uma máquina no E9 (arq 17); Redpanda de um nó sem fsync (arq 17, impl 3); fila no caminho de volta conta contra o agente (arq 11.5, 17); id determinístico como requisito ao agente (arq 10); E5 pode favorecer a chave desligada (impl 14); analistas simulados como hipótese (arq 17); premissas de volume e taxa de escala como hipótese (arq 3); marca fixa no contrato (arq 5, 17); resultados ainda não medidos (previsões marcadas como tais).

---

## 5. Aplicada a lista, chega a 10?

**Sim, pela régua, nas duas notas**, com três condições:

1. **As sete decisões do usuário (3, 12, 16, 19 a 22) precisam ser tomadas.** Qualquer escolha coerente serve para o desenho; a nota só não chega a 10 se a decisão ficar pendente ou se a alternativa escolhida não for declarada com o efeito (por exemplo, sem envelhecimento e sem declarar a fome). Na viabilidade há uma exceção: manter a fatia 2 inteira em uma semana, o E9 e o E8 na janela de dois dias e todo o front na semana 4 deixa o plano contra a velocidade medida. Isso é corrigível, então a nota de viabilidade fica em ~8 nesse caso.
2. **A rodada 4 precisa conferir as correções.** Nas três rodadas, cada correção certa abriu outra peça (seção 3). Os itens 1, 2, 5, 6 e 19 mexem em mecanismo e são os candidatos a isso.
3. **"10 de viabilidade" quer dizer plano crível com o risco declarado, não entrega garantida.** O cronograma foi estimado com uma fatia parcial medida; isso entra como limite honesto em arq 19.1 ("estimativa com uma fatia medida; recalibrada em 30/11 e a cada marco"), e a partir daí só a execução move a nota.

O que nenhuma correção de texto resolve, e por isso não pesa: qualidade do agente e do resumo, capacidade de produção, falhas de cluster, carga humana real. Todos estão na lista de limites declarados (seção 4, fim, e item 24).

---

## 6. Adendo: entrega em 23/11 (premissa nova)

Premissa trazida pelo usuário depois das seções 1 a 5: a entrega é em **2026-11-23**, não em 16/12. Restam ~2 dias. O usuário faz só o front-end; o backend inteiro fica com um agente de código. **Esta seção substitui os itens 19 a 23 da seção 4 e a nota de viabilidade da seção 3.**

### 6.1 Viabilidade contra o prazo novo

O plano escrito (arq 19 e 19.1: nove fatias, marcos semanais, cortes A a D) não cabe em 2 dias nem com todos os cortes aplicados. Hoje existem o compose, 3 tabelas e o envelope sem as regras. **Viabilidade do plano como está escrito: 2 / 10 em todos os critérios.** O desenho (seções 7 a 17 da arq) continua valendo como arquitetura-alvo; o que muda é o que se entrega e o que se declara.

Dois conflitos de processo antes de qualquer código:
- O `CLAUDE.md` exige ritual por parte (ficha, ok do usuário, modo misto com o trecho central escrito pelo usuário, commit só depois de ver). Com o agente fazendo todo o backend em 2 dias, o ritual precisa ser suspenso no backend. Isso é `decisão do usuário`. **Recomendação:** suspender o ritual no backend até 23/11 e manter dois pontos de controle (fim do dia 1 e meio do dia 2). Em cada um, o agente entrega uma página com o que fez, por quê e as três perguntas de banca de cada componente. O usuário precisa defender o que não escreveu.
- Front e back em paralelo só funcionam com a API congelada cedo. A primeira entrega do agente, nas primeiras 2 h, é o OpenAPI e os payloads de exemplo de todas as rotas que o front usa.

### 6.2 Corte de escopo para 2 dias (item 26, `decisão do usuário`, com recomendação)

**Entra (núcleo mínimo, um item por requisito):**

| Req. | O que entra | Simplificação declarada |
|---|---|---|
| 1 Canais | `POST /mensagens` com `canal` (chat, whatsapp, email) e `id_externo`; simulador = script e front | Sem regras próprias de canal (janela de 24 h, encadeamento de e-mail) |
| 2 Filas configuráveis | `versoes_regras` (JSONB, versão imutável, ativar, rollback, validação de campo, operador e valor), roteador puro, editor JSON no front | Sem re-roteamento de fila removida e sem envelhecimento |
| 3 Triagem e distribuição | Triagem por palavras-chave (categoria, prioridade, pedido de humano); distribuidor em laço de 1 s, uma conversa por transação, grupos ordenados IA → equipe, capacidade humana por conversa aberta | IA sem limite de capacidade (resolve N1); sem disjuntor |
| 4 Integração | Outbox e relay (um item por transação, retentativa com backoff, `erro` com escala por `falha_integracao`), inbox nas pontas, id determinístico, broker (ack do Kafka antes do 200; offset depois do 2xx do núcleo; 4xx para `helpdesk.erros`; 503 com pausa), mock com latência e modos `normal`, `duplicar`, `fora` | Sem `agente.processando`; versão `^1\.\d+$` no envelope |
| 5 Interface | Front do usuário: chat simulado, painel do analista com fila de escalas, contexto e histórico, editor de filas | Leitura a cada 2 s |
| 6 Handoff | Escala volta ao roteador com `origem = escalado`; fila de escalas; resumo do mock com `fontes`, ou resumo de reserva extrativo; analista assume e responde | Devolução para a IA só se sobrar tempo |
| 7 Auditoria | `eventos` só de inserção (trigger), `decisao_roteamento` e `decisao_distribuicao` | — |
| 8 Memória | Últimas N mensagens lidas sob a trava; perfil com `contatos_30d`, `escalas_30d` e `ultimo_assunto` | Sem identidades entre canais nem reabertura |
| 9 Volume e falhas | `transicionar` com trava, transições permitidas e fencing; `timeout_agente` desde o ack (agendador mínimo, só esse tipo); chaves `OUTBOX_ATIVA` e `INBOX_ATIVA`; juiz nas pontas; E1, E3b e E6 | Ver 6.3 |

**Sai e vira Evolução** (arq 21, com o desenho já escrito e as correções desta revisão anotadas): disjuntor e política `reter`/`transbordar` (N2, N9); heartbeat e renovação; inatividade e SLA; reabertura; identidades e fusão; envelhecimento (N3); capacidade da IA (N1); devolução, se não couber; reconciliador como serviço com banco próprio (fica um script SQL com I1 a I4 rodado no fim de cada execução); Prometheus e Grafana (ficam logs JSON e contadores no `GET /metricas`); várias instâncias.

**Sai do experimento e vira limitação declarada:** E2, E3, E4, E4b, E5, E7, E8 e E9; H2 e H3 ficam como "desenho pronto, não medido". Medem-se só H1 no E3b e no E6, mais a p95 interna no E1.

### 6.3 Experimento mínimo

- Carga pela agenda pré-gerada com semente (item 10): 8,3 conversas/s, 6 mensagens a cada 84 s, 7 min de aquecimento e 5 min medidos. Se a máquina não sustentar, cair para 50 msg/s e declarar.
- Juiz com os itens 6(a), 6(c), 6(d) e 6(e). Previsões com os itens 4 e 6(d). `RELAY_WORKERS` dimensionado (item 9, só a parte do relay).
- 3 cenários × 2 posições × 1 repetição ≈ 6 execuções de ~12 min. Segunda e terceira repetições só se sobrar tempo, declarado. CSV bruto e script das tabelas (item 13).

### 6.4 Plano de 2 dias

| Quando | Agente (backend) | Usuário (front) | Marco e piso |
|---|---|---|---|
| Dia 1 manhã | OpenAPI congelado; migration 0002 única; `transicionar`, outbox e relay, inbox; broker; mock | Telas de chat e acompanhamento sobre o OpenAPI, com dados de exemplo | 12h: mensagem vai e volta pelo broker |
| Dia 1 tarde | Agendador do timeout; roteador e versões; distribuidor; escala com resumo; auditoria; testes de 13.1 nesse escopo | Painel do analista e editor JSON | Fim do dia: escala por timeout chega ao painel. **Piso:** se não chegar, a devolução e a memória saem e o dia 2 começa pelo handoff |
| Dia 2 manhã | Chaves de ablação, juiz, agenda de carga, script do reconciliador; rodar E1, E3b, E6 | Integração real com a API | 13h: tabela com uma repetição. **Piso:** sem tabela, roda só o E6 com as duas posições |
| Dia 2 tarde | README com subida em um comando, limitações (item 24 e 6.2), tabelas | Roteiro de demo reduzido | — |
| Dia 2 noite | Gravação de reserva de cada falha | Ensaio | 23/11 fica só de folga |

Roteiro de demo (19.2) reduzido para o escopo: mensagem vai e volta; troca de regra sem deploy; broker derrubado com zero perda e reenvio deduplicado; mock derrubado com escala por timeout e analista assumindo com resumo; tabela do E3b e do E6; limitações. O trecho do disjuntor sai.

### 6.5 Efeito na lista da seção 4

- **Continuam obrigatórios para a entrega:** 4, 6 (sem 6b), 9 (relay), 10, 13, 16 (automático: o broker entra já), 17, 24 (acrescida da lista "Sai" de 6.2), 25.
- **Viram Evolução com a correção anotada, sem aplicar agora:** 1 (some: IA sem capacidade), 2, 3, 5, 11, 12, 14, 15.
- **Saem com o experimento:** 7, 8.
- **Substituídos pelo item 26 (6.2 a 6.4):** 18 a 23.

### 6.6 Notas com a premissa nova

| | Desenho | Viabilidade |
|---|---|---|
| Plano como está escrito (4 semanas) contra 23/11 | 7,0 (a arquitetura não muda) | 2 |
| Com o item 26 aplicado e os itens de 6.5 feitos | 7,5 a 8 (as contradições dos mecanismos cortados saem do escopo entregue e viram Evolução declarada) | 7 no plano |

**Chega a 10 pela régua?** No desenho, sim, nas mesmas condições da seção 5: o que sai fica declarado com o efeito, e o prazo é limite imposto, que não tira ponto declarado. Na viabilidade, a régua também permite 10, porque o corte é coerente e o prazo é imposto. Meu julgamento, porém, é que o plano de 2 dias tem risco alto de execução: backend inteiro feito por agente em ~1,5 dia, integração com um front feito em paralelo e um usuário que precisa defender código que não escreveu. Por isso 7, e não 10, enquanto três coisas não estiverem escritas na arq 19: os pisos de 6.4, o congelamento do OpenAPI e a decisão sobre o ritual. Com as três, a viabilidade do plano chega a 10 pela régua; daí em diante só a execução move a nota.
