# Revisão da arquitetura, rodada 1 (auditoria da revisão)

Data: 2026-11-20. Auditado: `docs/revisoes/rodada-1-validador.md`. Conferido contra `CLAUDE.md`, `docs/arquitetura.md` (arq), `docs/implementacao.md` (impl), `referencias.md`, `diferenciais.md`, `diario.md`, o código da fatia 1 e o histórico do git (`b7c86ac`, `b5af437`). Rodei `pytest testes` (sem gravar cache): 13 passam e 6 falham, todos da parte do Igor no `model_validator`, como previsto pelo ritual. Nenhum arquivo existente foi alterado.

Severidade: a mesma escala do validador (bloqueante, alta, média, baixa).

---

## 1. Qualidade da revisão

A revisão é tecnicamente sólida. Dos 35 itens, 26 procedem por inteiro, 9 procedem em parte e nenhum é falso. Os cálculos centrais (janela do disjuntor, retentativas de 61 a 123 s, Little) estão certos na forma.

Ela erra em detalhes de número e de localização (seção 5) e deixa passar cinco problemas que pesam: o contrato da fatia 1 não fecha a volta (N1), o juiz do experimento fica no meio e não nas pontas (N2), a semântica da ingênua não está definida (N3), Little calculado fora da carga do teste (N4) e o relay que trava inteiro, não só a conversa (A1 + M5).

---

## 2. Veredito item a item

`Sev. V` = severidade do validador; `Sev. A` = severidade desta auditoria.

| # | Sev. V | Sev. A | Veredito | Evidência e ajuste |
|---|---|---|---|---|
| B1 | bloqueante | bloqueante (parte código) + alta (parte métrica) | procede | Confere: CLAUDE.md "Fatia 1" ("o núcleo pode publicar direto no Kafka"); impl 5.1 (`eventos` só na fatia 2); impl 9, último parágrafo (I4 da ingênua "pelos eventos de auditoria"); migration 0001 linha 71 (`uq_mensagens_id_evento`); impl 7.6 (`id_derivado` no mock). Dividir: o que a ingênua **faz** precisa estar decidido antes da tag (bloqueante); como a tabela mede (I1, I3, I4, colunas) pode esperar a fatia 4 (alta). Falta no B1 o ponto mais imediato: a volta da fatia 1 nem passa no contrato (N1) |
| A1 | alta | alta, impacto maior | procede | impl 7.3 passo 4 chama `transicionar(..., para="escalada")` sem `id_atribuicao`; impl 6 não tem `escalada → escalada` nem `com_humano → escalada` para `sistema`. Agravante não visto: a exceção desfaz o lote de 50 (7.3: "travar, enviar e atualizar na mesma transação"), e a linha com erro é a mais antiga (`ORDER BY criado_em`), então entra em todo lote. O relay **inteiro** para, não só a conversa. Também: o teste 13.2 "evento que sempre falha ... escalada com `falha_integracao`" não pode passar para destino `broker`, porque o timeout de 30 s escala antes (arq 11.9 admite isso) |
| A2 | alta | alta | procede em parte | O ciclo existe: agendador trava `agendamentos` (7.4) e depois a conversa; `transicionar` trava a conversa e atualiza `agendamentos` (`encerrar_atribuicao`, `prazos_de_inatividade`). A frase "não há corrida" está na impl 7.8 (linha 643), não na arq 11.8 como diz o índice do validador. Ela é verdadeira para a semântica (a checagem sob trava protege o resultado); o defeito é deadlock, não corrida |
| A3 | alta | alta | procede | impl 7.4: o `timeout_agente` nasce "na mesma transação em que ... vai para a outbox". Atraso do relay, broker fora e reinício do núcleo contam contra o agente |
| A4 | alta | alta | procede, número corrigido | Forma certa (x ≈ 15 s, seção 3). O "~1.550 > ~1.200" compara cargas diferentes: 1.550 vale para 100 msg/s de cliente, e os 1.200 foram calculados para 2,9 conversas/s. Na mesma carga, as escalas antes de abrir ficam em cerca de 1/5 das conversas abertas com a IA, mais um lote. "Cerca de 70" segue falso. O item (c), sonda cancelada, só aparece depois de corrigir o (b): hoje as conversas retidas também geram desfechos no meio-aberto. Corrigir os dois juntos |
| A5 | alta | alta (a partir da fatia 5) | procede | impl 7.12 ("fora da transação") e 7.1 (o histórico não é relido sob a trava). Na fatia 2 não aparece, porque a atribuição nasce junto com a conversa |
| A6 | alta | alta | procede | Nem arq 11.1 nem impl 7.2 cobrem a entrada dos canais. Barato: coluna e índice na migration da fatia 2 |
| A7 | alta | alta | procede | impl 7.5 passo 5 contradiz arq 11.4 ("contrapressão, não perda"). A alternativa do validador (tabela de entrada crua no núcleo) é cara para o mês; a correção simples está em T9 |
| A8 | alta | alta | procede | impl 8 tem só `escolher`, função pura; não há laço, gatilho nem retentativa de `SemCapacidade`. Princípio 3 (arq 5) contra `escalada → com_humano` sem roteamento (arq 8) |
| A9 | alta | alta | procede em parte | Nenhum documento diz que o mock é um laço em série: é escolha de implementação ainda não feita. O defeito real é não haver modelo de concorrência nem de carga. Os números dependem da unidade de msg/s, que o próprio validador diz ser ambígua. Há solução mais simples que o controle de offsets contíguos (T25) |
| A10 | alta | alta, agravado | procede, com ajustes | Conferi a fonte: "answered within seven minutes, compared to the 22 minutes it took for the human analyst to resolve the issue". É tempo de atendimento, não tempo em sistema. Dois exageros do validador: a página **não** traz taxa de escala (os 25% são a parcela humana dos atendimentos, não escalas), e "dezenas de milhares" de e-mails abertos exige mais de ~7% das conversas como e-mail abandonado; com 5% são ~7.500. Agravante que ele não viu: no alvo do teste a chegada é 8,3 conversas/s, e L passa de 3.500 mesmo com 420 s (N4) |
| A11 | alta | média | procede | Regra 1:1 na impl 4.2 e cancelamento por `causado_por` exato na 7.4. O mock é nosso e obedece à regra, então o experimento não é afetado. É robustez de contrato e aderência, não perda no mês |
| A12 | alta | alta | procede | `transicionar` grava `mensagem.id_atribuicao = c.id_atribuicao_atual` depois do fencing. Nuance: com `criada_em = now()` (início da transação), o I4 pode dar **falso positivo** (transação que encerra a atribuição começou antes, pegou a trava depois e grava `fim` menor que `criada_em`). Na robusta, o I4 só erra para o lado falso; na ingênua da fatia 1 não há troca de dono. A coluna "Fora de dono" da parte 1 é zero por construção nas duas versões |
| A13 | alta | alta (decisão) | procede | CLAUDE.md "Plano de construção" (4 = Filas, 7 = Experimento) contra arq 19 (4 = Experimento parte 1); decisão 6 do CLAUDE.md ("prioridade com envelhecimento") contra arq 20 linha 10 (Evolução); arq 20 afirma "status alinhados ao CLAUDE.md" |
| A14 | alta | alta, decidir já | procede | O diário confirma: passo 1 de 4 da fatia 1 no dia 3. O ritual (uma parte por turno, trecho central escrito pelo usuário) reduz a velocidade, e o plano não leva isso em conta. A decisão de escopo muda o que a ingênua precisa ter (B1), então sai junto com ela |
| M1 | média | média | procede em parte | `versao: Literal["1.0"]` contradiz o comentário da linha 30; o exemplo `evt_8f2a`/`conv_123` é recusado (o próprio teste `test_id_que_nao_e_uuid_e_recusado` prova). Ajuste: o envelope pode continuar recusando tipo desconhecido; quem tolera é o consumidor (audita e confirma em vez de mandar para a fila de erros). Assim `test_tipo_desconhecido_e_recusado` continua valendo |
| M2 | média | média | procede | Além do apontado: `id_fila` já é `Uuid` na migration 0001 (linha 41), então o slug do exemplo não cabe no banco de hoje |
| M3 | média | média | procede | impl 7.1: `auditar(...)` seguido de `raise` é desfeito pelo rollback; o teste 13.1 "rejeitada e auditada" não passa como escrito |
| M4 | média | média | procede | impl 3 (produtor de `helpdesk.erros`: núcleo e broker) e 7.3 passo 4; arq 11.1 dá inbox ao broker e a impl 7.2 não; o broker não tem banco (impl 2) |
| M5 | média | alta | procede | Junto com A1, um lote de 50 numa transação transforma uma linha ruim em relay parado. HTTP dentro da transação segura travas por 50 × timeout |
| M6 | média | baixa | procede em parte | Conferi: o modo de desenvolvimento do Redpanda "acknowledges a message as soon as it is received without waiting for it to fsync". Nenhum cenário (E1 a E12) derruba o Redpanda, então a correção "não matar o Redpanda" já vale. Fica só a declaração nas limitações. A página descreve `development`; o compose usa `dev-container`, que não conferi em separado |
| M7 | média | média | procede | Não há índice para `conversas_ativas` em `atribuicoes` (impl 5.2); I3 sem índice em `causado_por` |
| M8 | média | baixa (decisão) | procede em parte | Conferi: no `HEAD`, a arq 19 tinha 8, 9 e 12 a 19 como Proposta; o `Contexto_projeto/CLAUDE.md` do `b7c86ac` (commit do próprio usuário) já as listava como "Decisões já tomadas" (itens 10 e 13). Há base do usuário; falta só a confirmação explícita. O caminho certo no commit é `Contexto_projeto/CLAUDE.md`, não `CLAUDE.md` |
| M9 | média | média | procede em parte | Contagem confere (593 → 954, 616 → 1.159, 191 → 324). A soma dos cortes listados pelo próprio validador (~380 + ~250 + ~100) dá ~30% dos três arquivos, não 40% (seção 8) |
| M10 | média | média | procede | Chatwoot conferido no `trigger.rb` (develop): 429 e 500 do agent bot viram erro retentável; outras falhas abrem a conversa para humano, salvo `keep_pending_on_bot_failure`. A frase da arq 6 é meio verdade |
| M11 | média | baixa | procede em parte | Plausível, mas sem medição. Fica sem efeito se a memória semântica sair (D-2) |
| L1 | baixa | baixa | procede | arq 2 (memória = 9) contra CLAUDE.md (memória = 8, volume = 9) |
| L2 | baixa | baixa | procede | |
| L3 | baixa | baixa | procede | arq 9 "O reconciliador só lê" contra impl 9 (grava `violacoes`) |
| L4 | baixa | baixa | procede | |
| L5 | baixa | baixa | procede | `modelos.py`: `atualizada_em` sem `onupdate`; `estado` sem `CHECK` |
| L6 | baixa | baixa | procede | |
| L7 | baixa | baixa | procede | |
| L8 | baixa | baixa | procede em parte | O README não está vazio: tem 16 bytes, só o título `# Case_CloudWalk`. A substância procede |
| L9 | baixa | baixa | procede em parte | A correção proposta (`pgvector/pgvector:pg16`) é uma tag flutuante, contra a regra da impl 2 ("fixar as versões das imagens"). Existem `0.8.0-pg16` a `0.8.7-pg16` no Docker Hub |

---

## 3. Cálculos refeitos

**Retentativas do relay (A1).** `atraso(t) = U(teto/2, teto)`, com `teto = min(60, 0,5 × 2^t)` e t de 1 a 7 antes da 8ª falha. Mínimo 0,5 + 1 + 2 + 4 + 8 + 16 + 30 = 61,5 s; máximo 1 + 2 + 4 + 8 + 16 + 32 + 60 = 123 s, sem contar o timeout de cada requisição. Confere com o validador. Como 30 s < 61,5 s, o timeout sempre escala antes.

**Disjuntor (A4).** Janela de 60 s e taxa de 50%. Em t0 + 30 + x, a janela tem r(30 − x) sucessos e r·x falhas; a taxa é x/30 e passa de 50% em x = 15 s. Confere. Escalas antes de abrir ≈ 15r + 50 (um lote), limitadas às conversas com a IA. Na mesma carga, r = L/70, porque cada conversa manda 6 mensagens de cliente em 420 s. Então 15r ≈ 0,21 L.

| Carga | r (cliente/s com a IA) | L (420 s) | Escalas antes de abrir | Sem disjuntor, queda de 60 s |
|---|---|---|---|---|
| Pico de estresse (2,9 conversas/s) | ~17 | ~1.200 | ~310 | ~1.200 + 2,9 × 60 ≈ 1.400 |
| Alvo 100 msg/s totais (8,3 conversas/s) | ~50 | ~3.500 | ~800 | ~4.000 |
| Alvo 100 msg/s de cliente (16,7 conversas/s) | ~100 | ~7.000 | ~1.550 | ~8.000 |

O disjuntor ainda corta perto de 80% das escalas, então H2 continua plausível. "Cerca de 70" só vale com janela por contagem (10 falhas em 20) e reavaliação a cada item; com reavaliação por lote de 50, ficam ~50 a 60.

**Little (A10, N4).** L = λ × tempo em sistema.

| Cenário | λ (conversas/s) | Tempo em sistema | L |
|---|---|---|---|
| Arq 3 (como está) | 2,9 | 420 s | ~1.200 |
| Alvo do teste, 100 msg/s totais | 8,3 | 420 s | ~3.500 |
| Estresse com 25% passando por humano (hipótese, a fonte não traz a taxa) | 2,9 | 0,75 × 420 + 0,25 × 1.740 = 750 s | ~2.200 |
| Alvo do teste com a mesma hipótese | 8,3 | 750 s | ~6.250 |
| E-mail abandonado, 5% das conversas, 72 h (λ médio diário 0,58/s) | 0,029 | 259.200 s | ~7.500 |

Conclusão: `CAPACIDADE_IA = 2000` (impl 10) estoura no E1 com o próprio número da arq. Na fatia 2 a conversa é atribuída na entrada, então `SemCapacidade` vira erro no `POST /mensagens` em ~4 min de E1.

**Vazão do mock (A9).** Com 800 ms por mensagem em série, cada partição faz 1,25 msg/s e 12 partições fazem 15 msg/s. Para 50 msg/s de cliente, Little dá 40 respostas em voo. Confere, se o mock for implementado em série.

---

## 4. O que o validador não viu

| # | Sev. | Onde | Problema | Correção (item do plano) |
|---|---|---|---|---|
| N1 | bloqueante | `contrato/envelope.py` (regra 2, parte do Igor) e `testes/test_contrato.py` linhas 84 a 98; CLAUDE.md "Fatia 1" ("podem ficar nulos"); arq 10 linha 315; impl 7.6 ("mesmo `id_atribuicao`") | Os eventos do agente exigem `id_atribuicao`, mas a fatia 1 não tem atribuição. O mock ecoa nulo e o núcleo recusa a resposta: o passo 3 da fatia 1 (volta) não fecha. O Igor está para implementar a regra que bloqueia o próprio esqueleto | T1 |
| N2 | alta | arq 11.6 e 17; impl 9 e 14 | O juiz fica no banco, no meio do caminho, embora o projeto cite Saltzer. Mensagem perdida antes de gravar (500 na entrada, SIGKILL no meio do `POST` no E7, `SemCapacidade`) e resposta gravada mas não entregue ao canal não aparecem no I1. "Perdidas (I1)" subconta justo nos cenários de falha | T22 |
| N3 | alta | CLAUDE.md "Fatia 1"; impl 9 e 14 | A ingênua não tem semântica escrita: publicar antes ou depois do commit, `enable_auto_commit` do consumidor (padrão `True` no aiokafka), o que fazer com `IntegrityError`, qual mock roda com ela (o da tag não tem `POST /modo`, então E3, E4 e E5 não se injetam nela). Do jeito que está, a falha aparece ou não por acaso | T2 (depende de D-1) |
| N4 | alta | arq 3; impl 10 | Little calculado com 2,9 conversas/s (pico de estresse), enquanto o teste roda a 100 msg/s (8,3 conversas/s ou 16,7, conforme a unidade). A capacidade da IA estoura no E1 | T11 |
| N5 | média | impl 7.3 (`NOT EXISTS` sem `destino`); arq 11.3 | A ordem da outbox é por conversa, não por conversa e destino. Uma falha no envio ao canal segura por até 123 s a `mensagem.recebida` seguinte para o agente, e o inverso também | T21 |
| N6 | média | impl 7.5 passo 6 | "Não confirma, espera e tenta de novo, sem limite" num laço bloqueante passa do `max_poll_interval_ms` do aiokafka (padrão 300.000 ms): o consumidor é dado como morto e o grupo rebalanceia. A contrapressão precisa de `pause()`/`resume()` da partição, seguindo com `getmany()` | T9 |
| N7 | média | arq 11.2, 11.3 e 11.6 (números de Yuan, Bailis, ACIDRain); referencias 6.1 ("devem ser conferidos no texto completo antes ... da banca") | A arq apresenta como fato números que a própria referências diz não terem sido conferidos no texto completo. Mesma falha de rótulo que o validador apontou no MTEB-PT, só que maior | T20 |
| N8 | baixa | arq 17 H1 | H1 diz que a ingênua não zera perdas e duplicatas. No E1, sem falha injetada, ela deve zerar, e a hipótese sai falsa por redação | T23 |
| N9 | baixa | `contrato/envelope.py` linha 31 | `frozen=True` é raso: `dados` continua um `dict` mutável. "Ninguém altera no caminho" não é garantido | T14 |
| N10 | baixa | impl 7.9 (prorrogação) | A prorrogação de conversa retida fecha o agendamento como `timeout` e abre outro. Com o disjuntor fechado de novo, esses desfechos entram na janela como falha, inflando a taxa | T6 |

---

## 5. Erros da própria revisão

| Item | Erro | Correto |
|---|---|---|
| A4, seção 3 | "~1.550, mais do que os ~1.200 sem disjuntor" | Cargas diferentes; na mesma carga, ~21% das conversas com a IA mais um lote |
| A10, seção 3 | "25% escaladas (2023)" atribuído à fonte | A página não traz taxa de escala; 25% é a parcela humana dos atendimentos |
| A10 | E-mail com "dezenas de milhares" | Milhares, salvo se mais de ~7% das conversas forem e-mail abandonado |
| índice de contradições | "arq 11.8 'não há corrida'" | Está na impl 7.8 |
| M8 | "o CLAUDE.md, no commit `b7c86ac`" | `Contexto_projeto/CLAUDE.md` |
| M9 | "cerca de 40%" | ~30% pela soma dos próprios cortes |
| L8 | "Vazio (0 bytes)" | 16 bytes, só o título |
| L9 | `pgvector/pgvector:pg16` | Tag fixa, ex. `0.8.7-pg16`, pela regra da impl 2 |
| seção 1 | Desenho "6,0" | A média das linhas dele é 5,9 |

---

## 6. Calibração das notas

| Critério | Validador (D / V) | Auditoria (D / V) | Por quê |
|---|---|---|---|
| Aderência e coerência | 7 / 6 | 6,5 / 6 | Soma-se N1 (código contra a especificação da fatia atual) e N5 |
| Filas configuráveis | 6 / 6 | 6 / 5 | Desenho certo; a viabilidade cai porque filas são a fatia 5, na semana 3, e o distribuidor nem está escrito |
| Robustez da integração | 6 / 5 | 5 / 5 | Primitivas certas, mas A1 + M5 param o relay inteiro, A2 e A7 falham nos próprios cenários e a ingênua não tem semântica (N3) |
| Handoff com contexto | 5 / 5 | 5 / 4 | Fatia 6 depende do Next.js e do distribuidor (A8), na semana 3 |
| Evidência de escalabilidade | 4 / 4 | 4 / 4 | Concordo; N4 piora a premissa e o método do E9 é honesto |
| Honestidade nas limitações | 7 / 8 | 6 / 8 | O sistema de rótulos é bom, mas a arq usa números não conferidos (N7), "cerca de 70", "exatamente uma vez", H1 falsa por redação (N8) e uma coluna que só pode dar zero (A12) |
| Reprodutibilidade | 7 / 6 | 6 / 6 | Hoje só o compose sobe; sem gerador, sem semente e sem verdade de referência nas pontas (N2) |
| Demonstração | 5 / 4 | 5 / 4 | Concordo |
| **Geral** | **6,0 / 4,5** | **5,5 / 4,5** | Desenho levemente inflado (robustez e honestidade). A viabilidade sobe para ~6 se D-1, D-2 e D-3 forem decididos esta semana |

---

## 7. Plano de correção

Ordem: P0 antes de fechar a fatia 1 (e antes de o Igor implementar a regra 2); P1 nos documentos, antes da fatia 2; P2 antes das fatias 3 e 4; P3 antes da fatia 5 em diante. Tudo que mexe em código passa pelo ritual (ficha, ok do usuário). O CLAUDE.md é do usuário: o redator só propõe o texto.

### 7.1 Decisões do usuário

| # | Pri. | Decisão | Opções (prós / contras) | Recomendação |
|---|---|---|---|---|
| D-1 | P0 | Linha de base do experimento (B1, N3) | **A. Tag da fatia 1 + tabela cenário × versão com "não se aplica"** (validador). Pró: mantém a decisão 13. Contra: E6 não existe na ingênua, I4 não se mede, e cada linha não diz qual mecanismo evitou a falha. **B. Ablação por chaves na robusta** (`OUTBOX_ATIVA`, `INBOX_ATIVA`, `FENCING_ATIVO`, `TIMEOUT_ATIVO`; desligadas = ingênua). Pró: mesmo broker, mesmo mock e mesmas tabelas; E6 vale nas duas; cada linha liga uma chave a uma falha, o que a arq 17 promete. Contra: um `if` por mecanismo no núcleo; a "ingênua" deixa de ser um sistema construído à parte e muda a decisão 13. **C. Tag da fatia 1 + broker repassador mínimo.** Pró: E6 passa a existir. Contra: mais código fora do plano; I4 e o mock continuam problemas | **B.** A tag `ingenua` fica como marco do esqueleto. Em qualquer opção valem T1 e T2 |
| D-2 | P0 | Escopo do mês (A14, M9, M11) | **A. Cortes da seção 8 do validador** (detector, casos parecidos, comparação de 3 modelos, SSE trocado por leitura a cada 2 s, contrato 1.1, I8, inbox do broker, D1 a D5). Pró: corta o que não pesa na nota. Contra: a memória semântica ainda custa serviço, pgvector e 100 consultas rotuladas. **B. A + memória semântica (D6) inteira para Evolução**, ficando a operacional (perfil + últimas N), que já atende o requisito 8. Pró: maior corte com menor perda de nota; some a fatia 7b, o E10 e o E11. Contra: o D6 foi aprovado pelo usuário; perde-se um diferencial visível. **C. A + D6 reduzido** (e5-small contra recência, sem detector e sem casos parecidos). Pró: mantém o diferencial medido. Contra: ~3 a 4 dias de trabalho na semana 4 | **B**, com C como bônus só se o marco da semana 3 for cumprido |
| D-3 | P0 | E4, E4b e E5 na parte 1, em que a robusta escala para humanos que só existem na fatia 6 (B1d) | **A. Parte 1 só com E1, E2, E3, E3b, E6 e E7** (perdas e duplicatas, H1); E4, E4b e E5 vão para a parte 2, junto do E8. Pró: compara o que as duas versões conseguem expressar. Contra: a parte 1 fica sem o cenário "agente fora". **B. Analistas simulados mínimos já na fatia 4.** Pró: mantém os cenários. Contra: puxa parte da fatia 6 para a frente. **C. Manter e declarar.** Contra: a banca pergunta "quem ganhou no E5?" | **A** |
| D-4 | P0 | Plano de fatias e papel do CLAUDE.md (A13) | **A. Adotar a ordem da arq 19** (com D-2 e D-3 aplicados) e reduzir o CLAUDE.md a ponteiros, ritual, regras e "onde paramos". Pró: uma fonte só. Contra: reescrever o CLAUDE.md. **B. Manter o CLAUDE.md e voltar a arq 19 para a ordem antiga.** Contra: o experimento volta para o fim, o risco que a arq 19 corrigiu | **A** |
| D-5 | P2 | Status das decisões (M8) | **A.** Confirmar como Decidida 8, 9, 13, 14, 15, 18 e 19 (princípio); voltar 16 e a segunda metade de 17 para Proposta até T3 e T9. **B.** Voltar tudo para Proposta e validar uma a uma. **C.** Manter como está | **A** |
| D-6 | P2 | Unidade de "100 msg/s" e pico do E2 (A9) | **A. 100 msg/s de cliente** (~200 totais, 16,7 conversas/s). Pró: mais exigente. Contra: muito acima da premissa (70 msg/s totais no pico concentrado). **B. 100 msg/s totais** (~50 de cliente, 8,3 conversas/s), coerente com a arq 3, que conta as duas pontas; E2 com rampa até 200 msg/s totais por 3 min. Contra: menos folga | **B** |
| D-7 | P2 | Disjuntor no mês (A4, N10) | **A. Simplificado**: janela por contagem (últimos 20 desfechos), meio-aberto só pelas sondas, aberto = não distribui para a IA + espera máxima, sem prorrogar quem já está com a IA. **B. Completo, corrigido.** **C. Cortar e declarar.** Contra de C: H2 e a falha metaestável são das melhores perguntas de banca | **A** |

### 7.2 Correções técnicas

| # | Pri. | Origem | Correção concreta |
|---|---|---|---|
| T1 | P0 | N1 | Ingênua: ao criar a conversa, `id_atribuicao_atual = gen_random_uuid()` (sem tabela `atribuicoes`); o núcleo manda esse id em `conversa.atribuida` e `mensagem.recebida`; o mock ecoa; o consumidor grava em `mensagens.id_atribuicao`, sem fencing. A regra 2 e os testes ficam como estão. Texto: CLAUDE.md "Fatia 1" ("`id_atribuicao` gerado por conversa, sem tabela de atribuições; `causado_por` preenchido pelo mock") e arq 10, linha 315. Avisar o Igor antes de ele implementar a regra 2 |
| T2 | P0 | B1c, N3 | Escrever na impl 9/14 a semântica da linha de base: grava no banco, confirma e só depois publica, sem retentativa; consumidor com `enable_auto_commit=True`; `IntegrityError` = log e segue (sem travar a partição); um mock só para as duas versões, com `POST /modo`, e a ingênua ignora os tipos que não trata. Declarar que `UNIQUE(id_evento)` da 0001 já protege a ingênua contra duplicata de mesmo id (a 0001 não se edita): o E3 com o mesmo id deve dar zero nas duas, e a diferença em duplicatas se mede no E3b (T8). Nas duas versões a resposta é entregue ao simulador de canal (na ingênua, `POST` direto depois do commit) |
| T3 | P1 | A1, M5, N6 | Relay: um item por transação; reserva curta (`status = 'enviando'`, `reservado_ate`, entra no `CHECK`); HTTP fora da transação; o resultado vai numa transação nova. Esgotou: `status = 'erro'` em transação própria. Destino `broker`: `transicionar(..., id_atribuicao=payload.id_atribuicao)`; atribuição já mudou ou conversa já escalada = `DESCARTADO` com auditoria, sem exceção. Destino `canal`: não escala; alerta e endpoint de reprocessamento. Trocar o teste 13.2 por "broker fora 3 min: nenhum laço, cada conversa escalada uma vez (por timeout), linhas em `erro` reprocessáveis" |
| T4 | P1 | A2 | Ordem de travas na impl 7.1: conversa → agendamento → atendente → disjuntor. Agendador: lê os ids vencidos sem travar; para cada um, numa transação: `SELECT conversa ... FOR UPDATE SKIP LOCKED` (ocupada = pula), relê o agendamento `WHERE status = 'pendente' FOR UPDATE` e age. Corrigir a frase da 7.8 para "a checagem sob trava evita corrida; a ordem de travas evita deadlock". Teste: resposta e vencimento no mesmo instante, 100 repetições, sem erro de deadlock |
| T5 | P1 | A3 | O `timeout_agente` nasce com `executar_em = now() + TIMEOUT_AGENTE_S + OUTBOX_LIMITE_S`; o relay, na transação que marca `enviado`, faz `executar_em = enviado_em + TIMEOUT_AGENTE_S` para `referencia = id_evento`. Carência: na subida, o agendador reagenda os `timeout_agente` vencidos para `now() + TIMEOUT_AGENTE_S`. Declarar que a fila no caminho de volta conta contra o agente |
| T6 | P2 | A4, N10 (com D-7) | Desfechos: janela pelos últimos `DISJUNTOR_MIN_AMOSTRAS`; reavaliação a cada item (sai de T4). Coluna `agendamentos.sonda boolean`; o meio-aberto conta só as sondas; sonda cancelada devolve a vaga (`sondas_restantes + 1`). Prorrogação fecha com `motivo_fim = 'prorrogado'`, fora da contagem. Trocar "cerca de 70" por "cerca de 10 (metade da amostra mínima)". E8 com quedas de 2 e 10 min; H2 sobre a carga humana total (`com_humano` + `escalada` + `na_fila` atendível por humano) e a espera p95 até a 1ª resposta |
| T7 | P3 | A5 | Histórico (últimas N) lido dentro de `transicionar`, sob a trava; só o vetor e o top-k ficam fora. `conversas.seq_mensagem` sobe a cada mensagem sob a trava. I1 exige que cada mensagem de cliente com `seq` maior que a última coberta tenha evento enviado ao atendente |
| T8 | P1 | A6 | Migration 0002: `mensagens.id_externo text` e `UNIQUE (canal, id_externo)`. `POST /mensagens` recebe `id_externo`; simuladores e k6 reenviam com o mesmo id em erro ou timeout. Cenário E3b: reentrega pelo canal (ingênua sem a coluna) |
| T9 | P1 | A7, N6 | Núcleo nunca devolve 500 por regra de negócio (transição inválida, descarte = 200 + auditoria); dependência fora = 503. Broker, na volta: 503 ou conexão recusada = contrapressão sem limite, com `consumer.pause(tp)`, espera com backoff e `resume(tp)`, sempre chamando `getmany()`; 4xx e esquema inválido = `helpdesk.erros`; 500 = `RETENTATIVAS_MAX`, depois `helpdesk.erros` com alerta, e o reprocessamento escala pela `id_atribuicao`. Não adotar a tabela de entrada crua |
| T10 | P3 | A8 | Laço do distribuidor a cada 1 s e depois de cada transição que libera capacidade: `SELECT ... FROM conversas WHERE estado = 'na_fila' ORDER BY prioridade_efetiva DESC, criada_em LIMIT 20 FOR UPDATE SKIP LOCKED`; para cada uma, `escolher` e `transicionar`. `SemCapacidade` vira resultado, não exceção: a conversa fica em `na_fila`. Escala: `escalada` = na fila humana com `origem = escalado`, roteada por `rotear` (fila de escalas por marca e equipe); `escalada → com_humano` pelo mesmo laço ou pelo analista que puxa com `SKIP LOCKED` |
| T11 | P2 | A10, N4 | Arq 3: recalcular L com a chegada do alvo do teste (tabela da seção 3), citar o release no 420 s como "tempo até resolver", não duração em sistema, e marcar a taxa de escala como hipótese. Capacidade da IA passa a contar trabalho em voo (mensagens com `timeout_agente` pendente), coerente com a justificativa "custo" da impl 10; humanos seguem por conversa aberta. Atualizar a decisão 1 (CLAUDE.md, com aval) |
| T12 | P2 | A11 | Evento do agente com `causado_por = X` cancela todos os `timeout_agente` pendentes da mesma atribuição criados até o de `referencia = X`. Várias `mensagem.enviada` por mensagem, com `id_derivado(causado_por, tipo, n)`. I3 = mesmo `(causado_por, sequencia)` ou mesmo conteúdo com ids diferentes. Id determinístico declarado como requisito do contrato nas limitações |
| T13 | P1 | A12 | `mensagens.id_atribuicao_declarada` (do evento) ao lado de `id_atribuicao` (vigente); I4 = as duas diferem. Tirar "Fora de dono" da tabela da parte 1 (zero por construção nas duas). I1 separa "sem desfecho" de "esperando humano". Ordenar por `seq_mensagem` (T7) ou gravar `clock_timestamp()` |
| T14 | P0 | M1, N9 | Contrato ainda sem consumidor: `versao` com `pattern=r"^1\.\d+$"`; `agente.processando` já em `TipoEvento` e `EVENTOS_DO_AGENTE` (versão 1.0) e a 1.1 deixa de existir (impl 4.1, 15; arq 10). O envelope segue recusando tipo desconhecido; o consumidor trata esse `ValidationError` como "audita e confirma". `dados` como `Mapping` imutável ou declarar a imutabilidade rasa. Exemplos com UUID no CLAUDE.md e na arq 10. É código da parte do Igor: entra por ficha |
| T15 | P3 | M2 | Validação de valores contra o domínio (`marca` em `marcas`, `canal`, `prioridade`); `"JIM"` → `"jim"`. Migration: `id_fila` como `text` (slug estável, igual ao registro de decisão). `atendentes` → lista ordenada de grupos `{"tipo": "ia"|"equipe", "id": ...}`. Versão ativa lida por roteamento (uma consulta indexada). Ao ativar, re-rotear `na_fila` de fila removida. Envelhecimento como expressão no `ORDER BY` (corrigir a arq 11.5, que o liga ao agendador) |
| T16 | P1 | M3 | `transicionar` devolve `Resultado.REJEITADO` / `SEM_CAPACIDADE` em vez de levantar exceção, e quem chama confirma a auditoria. `acao.executada` descartada pelo fencing é auditada com o payload inteiro e a marca `fora_da_atribuicao`. Resumo atrasado de `conversa.escalada` anexado à escala vigente. Trigger que recusa `UPDATE`/`DELETE` em `eventos` |
| T17 | P1 | M4 | O núcleo não publica no Kafka: `outbox.status = 'erro'` é a fila de erros dele, com endpoint de reprocessamento; o único produtor de `helpdesk.erros` é o broker (impl 3). Broker sem inbox (arq 11.1) |
| T18 | P2 | M6 | Limitações: "pelo menos uma vez, com deduplicação nas pontas que controlamos; canais e agente reais não deduplicam"; Redpanda em modo dev (confirma sem fsync) com um nó |
| T19 | P1 | M7 | Coluna `atendentes.ativas` atualizada sob a trava do atendente (ou índice parcial `atribuicoes (id_atendente) WHERE fim IS NULL`); índice `mensagens (causado_por) WHERE autor_tipo = 'ia'`; reconciliador por janela de tempo; limpeza diária de `outbox` enviada e `agendamentos` finalizados com mais de 7 dias |
| T20 | P2 | M10, N7 | Arq 6: "Chatwoot retenta 429 e 500 do agent bot; nas outras falhas, abre a conversa para humano, salvo a opção `keep_pending_on_bot_failure`" (fonte: código, não o fork). Overeem: "sistemas *event sourced*". Dai: "inferência nossa". COTA: "analogia; o COTA classifica e seleciona respostas". MTEB-PT: `[preprint, aceito no BRACIS]`. Cada número das seções 11 e 12 da arq com o nível de conferência (texto completo, resumo ou fonte secundária) |
| T21 | P1 | N5 | No `NOT EXISTS` da impl 7.3, acrescentar `AND p.destino = o.destino`: a ordem vale por conversa e destino; a sequência segue única por conversa |
| T22 | P2 | N2 | Verdade de referência nas pontas: o k6 grava `(id_externo, conversa, enviado_em, status)`; o simulador de canal grava as respostas entregues, com a cadeia `causado_por` até o `id_externo`. Perdida = enviada sem resposta entregue nem escala; duplicada = mais de uma resposta entregue para a mesma mensagem e sequência. I1 e I3 viram complemento. Comportamento de reenvio do k6 fixado (uma vez, mesmo `id_externo`) |
| T23 | P2 | N8 | Tabela de previsão por cenário e versão, escrita antes de rodar; H1 reescrita por cenário |
| T24 | P0/P1 | L1 a L9 | L1: numeração do enunciado. L2: I8 vira teste unitário. L3: reconciliador com banco próprio `reconciliador`. L4: declarar. L5: na migration 0002, `CHECK` com os seis estados e `atualizada_em` gravado em `transicionar`. L6: `pg_try_advisory_xact_lock`. L7: reabertura re-roteia e limpa `motivo_encerramento` e `resolvida_em`; timeout também na devolução. L8 (P0): README com os comandos de verificação do diário. L9 (P0, se o D6 ficar): `pgvector/pgvector:0.8.7-pg16` agora; se o D6 sair (D-2 B), apagar o parágrafo da impl 2 |
| T25 | P2 | A9 | Uma latência interna só (entrada → ack do broker, impl 11) e a arq 16 alinhada. Relay acordado a cada 100 ms, declarado. Envios do relay em paralelo entre conversas diferentes (depois de T3). Mock: consome; numa transação grava inbox + resposta com `publicar_em = now() + LATENCIA_MS`; confirma o offset; um laço publica as vencidas com produtor idempotente (sem controle de offsets contíguos). k6 com modelo de conversa: 6 mensagens de cliente, intervalo fixo, encerramento explícito e semente fixa |
| T26 | P1 | A13 (depois de D-4) | Propor o novo CLAUDE.md e tirar da arq 20 a frase "status alinhados ao CLAUDE.md" até estar verdadeira |

---

## 8. Inchaço

Estimativa do validador: 40%. Ajuste: a soma dos cortes que ele mesmo lista dá ~730 de 2.437 linhas, cerca de 30%. Os 40% valem só para a arq. Com D-2 B (D6 para Evolução) e SSE trocado por leitura periódica, o total chega a ~35%.

| Arquivo | Linhas | Corte realista | Observação |
|---|---|---|---|
| arquitetura.md | 954 | 300 a 380 (31% a 40%) | Seção 13 ~110; blocos "Base" ~67 linhas, que viram citação curta; 16, 17.1 e 18 duplicados; diagramas de 11.7 e 13.2 |
| implementacao.md | 1.159 | 230 a 270 (20% a 23%) | 4.4, 5.3, 7.11 a 7.14, E10 a E12b e variáveis de memória |
| referencias.md | 324 | ~90 (28%) | |

**Cortes mais seguros (não perdem decisão nem evidência):**
1. Status em três lugares: tirar "(proposta)" dos títulos e os parágrafos-ponte; fica só a tabela 20.
2. Blocos "Base" da arq viram "(Autor, ano)"; o texto fica em `referencias.md`.
3. Arq 16 (duplica impl 11 e 14), 17.1 (duplica impl 3 e 14) e 18 (duplica `diferenciais.md`).
4. Arq 19, "Por que mudou": vai para o diário.
5. Notas de processo em `referencias.md` ("link 404", "a página não abriu") viram um rótulo de conferência.
6. Parâmetros numéricos repetidos nas 11.7 a 11.9 e 13.x: apontar para a impl 10.
7. Com D-2 B: arq 13.2 a 13.7, impl 4.4, 5.3, 7.11 a 7.14, `incidentes`, E10 a E12b e as variáveis de memória vão para um anexo do D6.
8. Com T14: impl 4.1 "Ajuste no código quando a 1.1 entrar" e a linha correspondente da impl 15.

**Ajuste aos cortes do validador:** não apagar a seção 11 de `referencias.md` ("Indicados no TAPI"); ela mostra aderência ao enunciado e cabe numa linha. Na seção 2, manter o τ-bench, que sustenta o D2; cortar LLMCompiler, RouteLLM, PagedAttention e "Scalable LLM Agent Tool Access".

---

## 9. Evidência conferida nesta auditoria (2026-11-20)

Páginas lidas por ferramenta de leitura web, que resume o texto completo da página; os trechos entre aspas são do texto.

| Fonte | O que confere | Leitura |
|---|---|---|
| CloudWalk, "Generative AI brings $20 million return for Brazilian fintech CloudWalk", release, https://www.cloudwalk.io/newsroom-releases/generative-ai-brings-20-million-return-for-brazilian-fintech-cloudwalk | 75% dos atendimentos de 2023, ~2,6 mi de pedidos, mais de 1,2 mi de clientes, "answered within seven minutes, compared to the 22 minutes it took for the human analyst to resolve the issue". Sem taxa de escala | Página completa |
| Redpanda, "rpk redpanda mode", documentação, https://docs.redpanda.com/current/reference/rpk/rpk-redpanda/rpk-redpanda-mode/ | Modo de desenvolvimento: fsync ignorado e write caching que confirma `acks=all` "as soon as it is received without waiting for it to fsync". Descreve `development`, não `dev-container` | Página completa |
| Chatwoot, `lib/webhooks/trigger.rb`, branch develop, https://raw.githubusercontent.com/chatwoot/chatwoot/develop/lib/webhooks/trigger.rb | 429 e 500 do agent bot viram `RetryableError`; nas outras falhas, conversa `pending` vai para `open`, salvo `keep_pending_on_bot_failure`. Número de tentativas do job não conferido | Código completo |
| aiokafka, API, https://aiokafka.readthedocs.io/en/stable/api.html | `max_poll_interval_ms` padrão 300.000 (passou do limite, o grupo rebalanceia); `enable_auto_commit` padrão `True`; `pause()`/`resume()` sem rebalance | Primeiros 100 mil caracteres da página |
| Docker Hub, `pgvector/pgvector`, tags com `pg16`, https://hub.docker.com/v2/repositories/pgvector/pgvector/tags?page_size=100&name=pg16 | Existem `0.8.0-pg16` a `0.8.7-pg16`, além das flutuantes `pg16` | Listagem da API |

Não procurei fonte nova para a ablação (D-1 B): é desenho experimental, e a base já citada (Basiri et al., 2016) cobre a injeção de falhas.
