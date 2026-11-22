# Revisão da arquitetura, rodada 4 (validador)

Data: 2026-11-21. Premissa: entrega em 2026-11-23; backend por agente de código, front pelo usuário.
Lidos: `rodada-3-validador.md` (seções 4 e 6), `CLAUDE.md`, `arquitetura.md`, `implementacao.md`, `referencias.md`, `diferenciais.md`; código em andamento só para achar contradição grave (`nucleo/`, `broker/main.py`, `agente_mock/main.py`, `canais/main.py`, migration 0002, `contrato/envelope.py`, `docker-compose.yml`).

Régua: limitação declarada com o efeito não tira ponto; corrigível não feito, ou limitação escondida, tira. Abreviações: arq = `arquitetura.md`, impl = `implementacao.md`, D = desenho, V = viabilidade.

---

## 1. Itens obrigatórios da rodada 3 (6.5 e item 26)

| Item | O que pedia | Estado | Onde prova |
|---|---|---|---|
| 4 | Previsão do E6 com as escaladas do caminho de volta; 13.2 em dois casos | Resolvido | impl 14 (E6, as duas posições, "ordem de 40 a 60, hipótese"); impl 13.2 (sem mensagem em voo: nenhuma por timeout; com mensagem em voo: escala por `timeout`) |
| 6 (sem 6b) | Juiz com transferência vista na ponta, "esperando humano", "recusadas" e colunas novas | Resolvido no documento; ver N13 e N14 | arq 17 (regras do juiz); impl 6 (transferência com `causado_por`); impl 14 (tabela com Recusadas, Esperando humano, Espera p95); 6b adiada com motivo (impl 14: o mock responde cada mensagem) |
| 9 (relay) | Little por salto, `RELAY_WORKERS`, drenar antes de dormir, pool | Resolvido | impl 11 (tabela), 10 (`RELAY_WORKERS = 8`), 7.3 (drena até esvaziar); consumidor de volta sem dimensionamento, declarado (impl 11) |
| 10 | Carga por mensagem, agenda com semente | Resolvido | impl 14 ("Carga", `carga/agenda.py`, `constant-arrival-rate`, VUs em dezenas) |
| 13 | Recuperação definida, CSV bruto, `carga/tabelas.py`, sementes | Resolvido no documento; ver N18 | impl 14 ("Recuperação", "Registros"); impl 10 e 7.3 (`RELAY_SEMENTE`, `MOCK_SEMENTE`) |
| 16 | Broker desde a fatia 1 | Resolvido | impl 7.5 (último parágrafo), impl 12 (marco do dia 1, 12h) |
| 17 | Ordem de travas escrita igual à executada | Resolvido | arq 11.2; impl 7.1 (com a justificativa do `SEM_CAPACIDADE`) |
| 24 | Formato do contrato e limitações faltantes, mais a lista "Sai" | Resolvido | arq 2 (último parágrafo), arq 10 ("Formato do contrato"), arq 17 ("Limitações", 14 linhas), arq 19.1 (tabelas "Sai" com o efeito de cada corte) |
| 25 | Rótulo do Overeem | Resolvido | arq 10 ("vem de fonte secundária"); `referencias.md` |
| 26 | Corte por requisito, experimento mínimo, plano de 2 dias, pisos | Resolvido | arq 19.1 a 19.4; decisão 41 Decidida (arq 20) |
| 26, condição 1 | Pisos escritos na arq 19 | Resolvido | arq 19.3 (pisos do dia 1 e do dia 2); 19.1 ("Não sai") |
| 26, condição 2 | OpenAPI congelado cedo | Resolvido | arq 19.3 ("Processo"); impl 7.10 e 12 (primeiras 2 h; depois, só campos opcionais) |
| 26, condição 3 | Decisão sobre o ritual | Resolvido | `CLAUDE.md` ("Divisão do trabalho"); arq 19.3 (dois pontos de controle com página por componente e perguntas de banca) |

**Itens que viraram Evolução com a correção anotada (6.5):** 1, 2, 3, 5, 11, 12, 14 e 15 estão anotados onde a rodada 3 pedia (arq 21; impl 7.1, 7.9, 8, 14; arq 8 com a seta do E4). As decisões do usuário 3 (envelhecimento por `na_fila_desde`, Evolução com o efeito em arq 12) e 12 (vaga presa declarada em arq 12 e 17) foram tomadas. Item 18 fechado: "Não sai" virou os pisos, "semana 3" sumiu, H2 com 2 min e 10 min só bônus (impl 14, E8).

**Saldo:** todos os obrigatórios fechados no documento. O que sobra são contradições novas, quase todas pequenas, e duas que tocam o instrumento de medida (N13 e N14).

---
## 2. Regressões e contradições novas

| # | Sev. | Onde | Problema |
|---|---|---|---|
| N13 | alta (código × doc) | impl 6 ("transferência com `causado_por` = evento que escalou") × `nucleo/dominio/acoes.py` (`escalar` chama `para_canal` sem `causado_por`) | A mensagem de transferência sai com `causado_por` nulo nos três caminhos (timeout no agendador, esgotamento no relay, pedido do cliente) e no `conversa.escalada`. O juiz só conta escala por ela (arq 17); sem a cadeia, não sabe qual mensagem a transferência cobre. No E6 isso decide se as escaladas do caminho de volta aparecem como "escaladas" ou como "perdidas", isto é, se H1 passa na posição ligada. O documento está certo; o código não |
| N14 | média (desenho) | arq 17 e impl 14 ("cadeia `causado_por` até o `id_externo`") × impl 7.3 (com `OUTBOX_ATIVA = false` não há linha na outbox) | A cadeia não fecha nas pontas. A resposta entregue traz `causado_por` = id do `mensagem.recebida` ou do `conversa.atribuida` (a primeira mensagem da conversa vai dentro do `conversa.atribuida`, sem evento próprio). Quem liga esse id ao `id_externo` que o k6 gravou é só o núcleo, pela linha da outbox, e na posição desligada essa linha não existe. Resultado: o juiz do E1 e do E6 desligados, justamente a posição que prova H1, não tem como atribuir respostas a mensagens. Falta dizer onde a correspondência é gravada, nas duas posições da chave |
| N15 | média | arq 19.4 (2:50 a 3:50, `stop agente_mock` com k6 a 2 conversas/s) | Sem disjuntor (Evolução), toda conversa com a IA escala 30 s depois da próxima mensagem: L ≈ 2 × 420 ≈ 840 conversas com a IA, centenas de escalas no minuto do trecho, mais as novas, que continuam indo à IA. O painel do analista enche e o trecho de handoff fica ilegível. O roteiro também não religa o mock. No trecho do broker (1:50 a 2:50), as poucas respostas em voo escalam por timeout (N4 da rodada 3), e a fala "zero perda" precisa dizer "com algumas escaladas" |
| N16 | baixa | arq 7 (fluxo), 9 (Triagem), 12 (gatilho por sentimento) × arq 19.1 (triagem "categoria, prioridade, pedido de humano") × `nucleo/dominio/triagem.py` (calcula sentimento) | O escopo da entrega não diz se há sentimento. O código calcula; o 19.1 omite; o gatilho de escala por sentimento na plataforma não existe no código (só o pedido de humano em `nucleo/api/mensagens.py`; a irritação é escalada pelo mock). Resíduos do mesmo tipo: a nota da arq 7 não cita a inatividade como Evolução; arq 6 cita o disjuntor como melhoria sem dizer que é Evolução |
| N17 | baixa (código × doc) | arq 11.4 e impl 7.5 ("na entrega, 500 segue o passo 4, pausa sem limite") × `broker/main.py` (500 repetido vai a `helpdesk.erros` depois de `RETENTATIVAS_MAX`) | O código faz a versão Evolução, sem o reprocessamento que escala pela `id_atribuicao`. O efeito real é outro: o evento sai da partição e a conversa escala pelo `timeout_agente` pendente. Nada se perde, mas o documento descreve um comportamento que não roda |
| N18 | baixa (código × doc) | impl 7.3 e 10 (`random.Random(RELAY_SEMENTE)`) × `nucleo/infra/relay.py` (`random.uniform` global) | Jitter sem semente; a reprodutibilidade prometida não vale. E mesmo com semente, com 8 tarefas a ordem dos sorteios entre elas não é determinística; isso não está dito |
| N19 | baixa | impl 1 e 2 × `docker-compose.yml` e `canais/main.py` | O simulador de canais é serviço próprio (porta 8300, database `canais`), e é nele que o juiz lê as entregas. Não aparece na árvore nem na tabela de serviços |
| N20 | baixa | impl 13 (introdução: "os de roteador, versões, distribuidor e escala de 13.3") × 13.3 e 13.2 | Entram na entrega testes de mecanismo cortado: "fila removida re-roteia" (Evolução, 19.1), "IA com 800 de 2000" (IA sem limite), "Devolução com a IA no limite" e "I1 a I7" (só I1 a I4). O agente de código vai tentar escrevê-los ou vai deixá-los falhando |
| N21 | baixa | impl 14 (E3b "Simulador reenvia o mesmo `id_externo`"; E6 "`stop broker` por 60 s"; "Recuperação") | Faltam os parâmetros de injeção: fração e atraso do reenvio no E3b; instante da queda no E6 em relação à janela medida; quem injeta. Sem isso, duas execuções do mesmo cenário não são a mesma execução. A recuperação do E6 ligado também não tem previsão, embora seja conta simples (teto do backoff) |

**Conferência das correções da rodada 3 (seção 5, condição 2).** Os itens que mexiam em mecanismo e foram aplicados (4, 6, 9) não abriram peça nova no desenho, salvo a cadeia do juiz (N14), que já estava implícita no item 6 e só fica visível agora que a ablação da outbox tem código. O corte para 2 dias tirou de cena os mecanismos que vinham gerando regressões (disjuntor, sonda, capacidade da IA). Conferi a conta do E6 ligado: com `BACKOFF_BASE_S = 0,5`, teto 60 e 8 tentativas, os 7 atrasos somam de 61,5 a 123 s; 60 s de queda fica abaixo do mínimo, e a chance de a soma de sorteios cair perto de 61,5 s é desprezível. "Poucas ou nenhuma" está certo. A ordem por conversa e destino na reserva também é segura sob concorrência (a tarefa que pula a linha travada vê a anterior ainda `pendente` e não pega a seguinte).

---

## 3. Notas

Formato D / V. Na rodada 3, a coluna é a da seção 3 (plano de 4 semanas); com a premissa nova, a viabilidade daquele plano era 2.

| Critério | R1 | R2 | R3 | R4 | O que falta para 10 (seção 4) |
|---|---|---|---|---|---|
| Aderência e coerência | 7 / 6 | 7,5 / 7 | 8 / 7 | 9 / 9 | Sentimento e resíduos de texto (4), canais fora da impl 2 (6), broker 500 doc × código (5), testes de mecanismo cortado (7) |
| Filas configuráveis | 6 / 6 | 7 / 6 | 7,5 / 6 | 9,5 / 9,5 | Teste "fila removida re-roteia" listado na entrega (7). `reter` e envelhecimento saíram com o efeito declarado: não pesam |
| Robustez da integração | 6 / 5 | 7 / 6,5 | 7,5 / 6,5 | 9,5 / 9,5 | Broker 500 descrito diferente do que roda (5). Capacidade da IA, sonda e 500 com fila de erros viraram Evolução declarada |
| Handoff com contexto | 5 / 5 | 7 / 5,5 | 7 / 5,5 | 9,5 / 9 | Trecho de handoff da demonstração afogado em escalas (3). Vaga presa e devolução declaradas |
| Evidência de escalabilidade | 4 / 4 | 6 / 5,5 | 6,5 / 5,5 | 9 / 9 | Correspondência resposta → `id_externo` sem lugar na posição desligada (2); transferência sem `causado_por` no código (1); parâmetros de injeção e previsão de recuperação (8). E9 fora, H3 declarada: não pesa |
| Honestidade nas limitações | 7 / 8 | 7,5 / 8,5 | 8 / 8,5 | 9,5 / 9,5 | Dois pontos em que o documento promete o que o código não faz: broker 500 (5) e jitter com semente (5). Lista de limitações completa |
| Reprodutibilidade | 7 / 6 | 7 / 6,5 | 7,5 / 6,5 | 9 / 9 | Semente do relay e sua ressalva (5), parâmetros de injeção (8), juiz que depende do banco do núcleo na posição desligada (2) |
| Demonstração | 5 / 4 | 5,5 / 5 | 7 / 6 | 9 / 9 | Trecho do mock fora sem controle de carga e sem religar; fala do broker (3) |
| **Geral** | **6,0 / 4,5** | **6,5 / 5,5** | **7,0 / 6,0** (premissa nova: 7,0 / 2) | **9,0 / 9,0** | Média das linhas: 9,3 / 9,2 |

**Por que o geral fica abaixo da média.** H1 é a única hipótese medida, e o instrumento dela tem dois furos: a transferência sem `causado_por` (N13) e a correspondência resposta → `id_externo` que some quando a outbox está desligada (N14). Se ficarem, a tabela do E6, que é o centro da demonstração (3:50) e da evidência, sai sem conseguir separar "perdida" de "escalada". O resto da lista é texto de uma linha.

**Viabilidade.** As três condições da rodada 3 (pisos, OpenAPI congelado, ritual) estão escritas, então o plano é crível pela régua; o prazo, o agente de código e a defesa de código que o usuário não escreveu estão declarados (arq 19, `CLAUDE.md`). Pelo código, o backend está à frente do plano do dia 1 (relay, broker, agendador, roteador, distribuidor, painel e filas existem), mas ainda sem nenhum teste de 13.1 e sem `carga/`. Isso é execução, não item de documento, e não entra na nota. O que tira ponto da viabilidade é corrigível: N14 pode travar a manhã do dia 2 se for descoberto só quando o juiz for escrito.

**Progresso.** +2,0 / +3,0 sobre a rodada 3; +7 na viabilidade contra o plano de 4 semanas lido com o prazo novo. Pela primeira vez as correções da rodada anterior não abriram regressão de mecanismo; as contradições novas são de código contra documento ou de instrumento de medida.

---

## 4. Lista fechada do que falta para 10

Oito itens. Os itens 1 e 5 (segunda metade) são de código; os outros são texto pronto para colar. Nenhum pede decisão nova do usuário, salvo a escolha indicada no item 2.

1. **Transferência com `causado_por`** (N13; evidência, reprodutibilidade). Em `nucleo/dominio/acoes.py`, `escalar` recebe `causado_por` e o repassa a `para_canal`: timeout, `ag["referencia"]` (agendador); esgotamento, `item["id_evento"]` (relay); `conversa.escalada`, o `id_evento` dele; pedido do cliente, o evento de entrada `chave_entrada(canal, id_externo)`. Teste: escala por timeout grava no simulador uma transferência cujo `causado_por` é a `referencia` do agendamento. Precisa estar no código antes da primeira execução do E6.

2. **Onde a correspondência resposta → `id_externo` é gravada** (N14; evidência, reprodutibilidade, viabilidade). **Recomendação:** em arq 17 (juiz), depois da primeira frase: "A correspondência é gravada pelo núcleo, nas duas posições de `OUTBOX_ATIVA`: na transação que cria `mensagem.recebida` ou `conversa.atribuida`, as mensagens do cliente ainda não cobertas ganham `mensagens.id_evento_atendente` = id desse evento. Ao gravar uma resposta do agente, o núcleo põe na entrega ao canal `responde_a` = os `id_externo` das mensagens do cliente com `seq` até a maior ligada a esse evento e ainda sem resposta; a transferência leva os `id_externo` ainda sem resposta. O simulador grava `responde_a`, e o juiz casa só pelos registros das pontas." Em impl 5.2, a coluna `mensagens.id_evento_atendente uuid` com índice; em impl 14, "Juiz", a mesma regra. Isso também resolve a cobertura por `seq` (6b), porque a resposta à mensagem posterior leva os dois `id_externo`. Alternativa mais barata: o juiz lê só essa coluna no banco do núcleo, e arq 17 passa a dizer "a contagem vem das pontas; a correspondência evento → `id_externo` vem da tabela `mensagens` do núcleo, gravada nas duas posições da chave".

3. **Trechos de falha da demonstração** (N15; handoff, demonstração). Em arq 19.4, linha 2:50 a 3:50, coluna "Falha ao vivo": "k6 pausado; `stop agente_mock`; `start agente_mock` no fim do trecho e k6 retomado". Coluna "O que a plateia vê", acrescentar: "Fala: sem disjuntor (Evolução), todas as conversas com a IA escalariam do mesmo jeito; é a falha metaestável da 11.9, por isso a carga fica parada aqui". Linha 1:50 a 2:50: "zero perda; as poucas respostas que estavam em voo quando o broker caiu escalam por timeout e aparecem como escala, não como perda".

4. **Sentimento e resíduos de escopo** (N16; aderência e coerência). Arq 19.1, linha 3, coluna "Entra": "Triagem por palavras-chave (categoria, prioridade, sentimento, pedido de humano)"; coluna "Simplificação": acrescentar "sem gatilho de escala por sentimento na plataforma: escala por pedido do cliente e quando o agente escala (o mock escala por palavra de irritação)". Arq 7, nota abaixo do fluxo: "Na entrega, a retenção pelo disjuntor, a reabertura e a inatividade são Evolução, e a devolução só entra se sobrar tempo (19.1)". Arq 6, "Onde melhoramos": terminar com "fila de erros e disjuntor (o disjuntor é Evolução na entrega, 19.1)".

5. **Documento igual ao código no broker e no relay** (N17, N18; honestidade, robustez, reprodutibilidade). Arq 11.4, "Na entrega", e impl 7.5, passo 5, "Na entrega": "o 500 repetido vai a `helpdesk.erros` depois de `RETENTATIVAS_MAX`, sem o reprocessamento que escala pela `id_atribuicao` (Evolução); a conversa escala pelo `timeout_agente` pendente, então nada some sem aviso". Ajustar a linha correspondente da arq 21. No código, `relay.atraso` passa a usar `rng = random.Random(config.RELAY_SEMENTE)`, e `RELAY_SEMENTE` entra em `nucleo/config.py` e no `.env.example`. Impl 7.3, depois do bloco do `atraso`: "Com mais de uma tarefa, a semente fixa a sequência de sorteios, não qual item recebe cada um; o jitter é reproduzível em distribuição, não item a item".

6. **Simulador de canais nos serviços** (N19; aderência e coerência, reprodutibilidade). Impl 1, na árvore: `canais/  # simulador dos canais de saída; grava entregas e transferências (juiz)`. Impl 2, nova linha: "`canais` | 8300 | Recebe o que a plataforma envia ao cliente, inclusive a transferência; grava no database `canais`; `POST /modo` com `fora`". Na linha do `postgres`, acrescentar o database `canais`.

7. **Testes da entrega sem mecanismo cortado** (N20; aderência e coerência, filas). Impl 13, introdução, no lugar da primeira frase: "Na entrega: 13.1 sem as chaves de fencing e timeout; de 13.2, os de timeout, broker fora, deadlock, reinício e as violações plantadas de I1 a I4; de 13.3, roteador, versões sem o re-roteamento de fila removida, `escolher` sem o caso de capacidade da IA, distribuidor, isolamento por marca e escala. Devolução com a IA no limite, I5 a I7, disjuntor, heartbeat, inatividade, reabertura e fusão ficam com os mecanismos, em Evolução".

8. **Parâmetros de injeção e previsão de recuperação** (N21; evidência, reprodutibilidade). Impl 14, coluna "Como provocar": E3b, "10% das mensagens (inicial), sorteadas com `K6_SEMENTE`, reenviadas 2 s depois com o mesmo `id_externo`"; E6, "`stop broker` no minuto 8 (1 min dentro da janela medida), `start` 60 s depois, por `carga/falhas.py`". Impl 14, E6 ligado, acrescentar: "Recuperação prevista: até ~70 s depois da volta, dominada pelo teto do backoff (60 s); a drenagem dos ~3.500 eventos acumulados (~58/s × 60 s) leva segundos com 8 tarefas (hipótese)". Impl 1, na linha de `carga/`, citar `falhas.py`.

**Já declarados e corretos (não tiram ponto):** agente mock com texto fixo; uma máquina e uma instância; Redpanda de um nó sem fsync; dados sintéticos; prazo de 2 dias imposto; backend feito por agente de código, com os pontos de controle; E2, E3, E4, E4b, E5, E7, E8 e E9 fora, cada um com o efeito (arq 19.1); H2 e H3 não medidas; uma repetição, sem variância; contrato como proposta nossa; fila no caminho de volta conta contra o agente; vaga humana presa; sem envelhecimento; IA sem limite de capacidade; remover fila com conversas esperando as deixa sem atendimento; resultados ainda não medidos, com previsão escrita antes.

---

## 5. Aplicada a lista, chega a 10?

**Sim, nas duas notas, pela régua.** Os oito itens são corrigíveis em poucas horas somadas (os de texto em minutos; o 1 e o 2 em menos de uma hora de código), e depois deles não sobra contradição conhecida entre escopo, desenho, código e experimento, nem limitação sem efeito declarado.

Duas condições:
1. **Os itens 1 e 2 entram antes da primeira execução do E6**, não depois. Fora isso, a tabela que sustenta H1 pode sair sem separar perda de escala, e nenhum texto conserta uma medida já feita.
2. **Daqui em diante, só a execução move a nota.** Quando os resultados chegarem, a regra é a mesma das previsões: o que divergir do previsto vai para o README com a explicação, inclusive se a máquina não sustentar 100 msg/s e a carga cair para 50.

Esta foi a última rodada planejada. Não recomendo uma quinta rodada de desenho; recomendo uma conferência curta da tabela do E6 contra as previsões da impl 14 depois da primeira execução.
