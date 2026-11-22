# Revisão da arquitetura, rodada 2 (validador)

Data: 2026-11-21. Lido: `CLAUDE.md`, `docs/arquitetura.md` (arq, 654 linhas), `docs/implementacao.md` (impl, 791), `docs/referencias.md` (222), `docs/diferenciais.md`, as duas revisões da rodada 1 e o código da fatia 1 (`docker-compose.yml`, `nucleo/infra/modelos.py`, migration 0001, `contrato/envelope.py`). Nenhum arquivo existente foi alterado.

Severidade: a mesma da rodada 1. Não contam como erro novo, por combinação com o usuário: T14 no código (`envelope.py` aceita só `"1.0"` e não tem `agente.processando`), README (L8) e imagem do compose (L9).

---

## 1. Itens da rodada 1

| # | Status | Onde se prova (e ressalva) |
|---|---|---|
| B1 | parcial | Ablação em arq 17 e impl 14 resolve (a) broker, (b) I4 sem auditoria, (c) `UNIQUE(id_evento)` declarado no E3; D-3 tira E4/E4b/E5 da parte 1. Falta: a tabela da parte 1 não tem coluna de escaladas, e o timeout mascara a perda que o E6 e o E7 querem mostrar (R1); E3b desligado colide com o `UNIQUE (canal, id_externo)` (R2) |
| A1 | resolvido | arq 11.3; impl 7.3 passo 3 (erro em transação própria, fencing, canal não escala). Ressalva de texto em R6 |
| A2 | resolvido | arq 11.2 (ordem completa), 11.5; impl 7.4, 7.8; teste 13.2 de 100 repetições. O distribuidor reabre o problema por outro caminho (R4) |
| A3 | parcial | arq 11.5; impl 7.4 e 7.3 passo 1. O prazo antes do envio é `30 + OUTBOX_LIMITE_S (60)`: atraso da plataforma acima de 60 s ainda conta contra o agente (R6) |
| A4 | resolvido | arq 11.9; impl 7.9 (janela por contagem, só sondas, sonda cancelada devolve vaga), 13.3; E8 com 2 e 10 min; H2 sobre carga humana total. H2 tem defeito novo (R3) e a frase "abre depois de cerca de 10" omite o resto (R9) |
| A5 | resolvido | arq 11.2 passo 5 e 13; impl 7.1; I1 por `seq` (impl 9) |
| A6 | resolvido | arq 11.1; impl 5.2 (`UNIQUE (canal, id_externo)`), 7.2; E3b |
| A7 | resolvido | arq 11.4; impl 7.5 (503 = pausa da partição; 4xx = erros; 500 limitado). Resíduo em R14 |
| A8 | parcial | arq 12 e impl 8 escrevem laço, gatilho, `SKIP LOCKED`, `SEM_CAPACIDADE` como resultado e escala pelo roteador. O laço escrito tem bloqueio de cabeça de fila, ordem por texto e lote numa transação (R4) |
| A9 | parcial | Unidade (arq 3), latência única (arq 16, impl 11), mock assíncrono (impl 7.6), modelo de conversa no k6 (impl 14), relay paralelo (impl 7.3). Falta Little por salto: número de workers do relay e concorrência do consumidor de volta do broker não dimensionados (R19) |
| A10 | resolvido | arq 3 (fonte citada como "tempo até resolver", tabela com a meta do teste, 25% como hipótese); capacidade da IA por trabalho em voo (arq 12, impl 7.1, 10). Resíduo do lado humano em R10 |
| A11 | resolvido | impl 4.2 (várias respostas numeradas; cancela os prazos anteriores), I3 por `(causado_por, sequencia)`; arq 10, requisito do contrato. O juiz contradiz a regra (R8) |
| A12 | resolvido | impl 5.2 (`id_atribuicao_declarada`, `seq`), 9 (I1 separa "esperando humano", I4 declarada × vigente, ordem por `seq`); arq 11.6 |
| A13 | resolvido | `CLAUDE.md` só com ponteiros, ritual e regras; arq 20 sem "status alinhados" |
| A14 | parcial | D-2 aplicado (arq 13, 18, 21). Marcos não foram replanejados com a velocidade medida (pedido explícito da rodada 1); a lista "Não sai" segue longa (R18) |
| M1 | ritual | Texto resolvido (arq 10, impl 4.1); código é T14 |
| M2 | resolvido | arq 12; impl 5.1 (`id_fila` texto na fatia 5), 8 (validação de valor, grupos, versão por roteamento, re-roteamento); teste 13.3 com `"JIM"` |
| M3 | resolvido | arq 11.2; impl 7.1 (resultado em vez de exceção, `acao.executada` com payload, trigger). O retorno sem exceção criou R5 |
| M4 | resolvido | impl 3, 7.5; arq 11.1 (broker sem banco e sem inbox) |
| M5 | resolvido | arq 11.3; impl 7.3, 7.4 (um item por transação). O distribuidor ficou com lote de 20 (R4) |
| M6 | resolvido | arq 11 e 17; impl 3 |
| M7 | resolvido | impl 5.2 (`ativas`, índice parcial, índice em `causado_por`), 9 (janela), limpeza diária |
| M8 | resolvido | arq 20 conforme D-5 A (16 e 17b Proposta) |
| M9 | resolvido | 2.437 → 1.667 linhas nos três arquivos (−32%) |
| M10 | resolvido | arq 6 (Chatwoot pelo código), 10 (*event sourced*), 11.5 ("inferência nossa"); rótulos em `referencias.md` |
| M11 | sem efeito | D6 em Evolução |
| L1 | resolvido | arq 2 |
| L2 | resolvido | arq 11.6; impl 8 |
| L3 | resolvido | arq 9; impl 2, 9 |
| L4 | resolvido | arq 5 (princípio 6); impl 15 |
| L5 | resolvido | impl 5.2 (`CHECK`), 7.1 (`atualizada_em`) |
| L6 | resolvido | impl 7.4 |
| L7 | resolvido | arq 8; impl 6 |
| L8 | ritual | README com 16 bytes |
| L9 | ritual | Com o D6 fora, nenhum doc depende mais de pgvector; o compose segue `postgres:16-alpine`, o que agora está certo |
| N1 | resolvido | arq 10 e 19; impl 4.1 (id por conversa, mock ecoa). A regra 2 do Igor fica coerente |
| N2 | resolvido | arq 17; impl 14. Ressalva: "nem escala" vem do banco, não da ponta (R1) |
| N3 | resolvido | Trocado pela semântica de cada chave (impl 7.2, 7.3, 7.4). Ressalva em R2 |
| N4 | resolvido | arq 3; impl 10 |
| N5 | resolvido | arq 11.3; impl 7.3 (`p.destino = o.destino`); teste 13.1 |
| N6 | resolvido | impl 7.5 passo 4 |
| N7 | resolvido | arq 11, abertura ("conferidos pelo resumo"); legenda de `referencias.md` |
| N8 | resolvido no texto | H1 por cenário (arq 17). As previsões de E6 e E7 desligados não batem com o que o juiz mede (R1) |
| N9 | resolvido | impl 4.1 declara a imutabilidade rasa |
| N10 | resolvido | Versão simplificada sem prorrogação (arq 21) |

**Contagem (45 itens):** 36 resolvidos, 5 parciais (B1, A3, A8, A9, A14), 0 não resolvidos, 3 pendentes do ritual (M1, L8, L9), 1 sem efeito (M11).

---

## 2. Problemas novos ou deixados pelas correções

`arq` = arquitetura.md, `impl` = implementacao.md. Nenhum é bloqueante para fechar a fatia 1; os altos precisam estar resolvidos antes da fatia que usa o mecanismo.

| # | Sev. | Onde | Problema | Correção |
|---|---|---|---|---|
| R1 | alta | impl 7.4 (`timeout_agente` nasce com `now() + 30 + 60`), 14 (E6, E7, tabela da parte 1); arq 17 (H1, juiz) | **O timeout mascara a perda que a ablação quer mostrar.** O juiz conta como perdida a mensagem "sem resposta entregue nem escala". Com `OUTBOX_ATIVA = false` e as outras chaves ligadas, o `POST` que falha no E6 deixa um `timeout_agente` que nunca é encurtado e vence em 90 s: a conversa escala. Resultado previsível do E6 desligado: zero perdas e milhares de escaladas, contra "Perdas" na previsão. No E7, o mesmo. A parte 1 roda antes dos humanos (fatia 6): escalar é mandar para ninguém, o B1(d) de volta pela porta do E6. As colunas "escaladas" e "espera até a 1ª resposta", pedidas no B1(4), não estão na tabela da parte 1. E a escala que o juiz aceita vem do banco, não da ponta | `timeout_agente` só nasce no ack do broker (o relay o cria na transação que marca `enviado`); antes do envio, o único caminho de escala é o esgotamento do relay. Corrige também R6. Colunas "escaladas" e "espera até a 1ª resposta" na parte 1; escala vista na ponta (mensagem de transferência pelo canal, gravada pelo simulador) |
| R2 | alta | impl 7.2 ("a entrada ignora `id_externo`"), 5.2 (`UNIQUE (canal, id_externo)`), 14 (E3b; "mesmas tabelas") | **E3b desligado não produz duplicata, ou cega o juiz.** Se a entrada desligada grava o `id_externo`, o `UNIQUE` do banco deduplica e a chave não desliga nada (H1 sai falsa). Se não grava, a cadeia do juiz ("`causado_por` até o `id_externo`") quebra: as duas respostas não se ligam à mesma mensagem enviada. "Mesmas tabelas" e "chave que desliga a deduplicação" não cabem juntas com a deduplicação num índice único | Deduplicar `id_externo` pela inbox (`eventos_processados` com chave `canal:id_externo`), não por `UNIQUE`; gravar sempre `id_externo` em coluna indexada sem unicidade, para a cadeia do juiz. Teste de 13.1 com a chave desligada |
| R3 | alta | arq 12 ("a equipe recebe quando a IA está ... com o disjuntor aberto") × arq 11.9 ("o que se protege é a fila humana"); impl 7.9; H2 | **Disjuntor aberto transborda para humanos, e H2 mede o contrário.** Com `atendentes` como grupos ordenados (T15), fila AI first com equipe em segundo manda a conversa nova direto à equipe quando o disjuntor abre; só fila sem equipe retém. Sem disjuntor, a mesma conversa iria à IA, venceria em 30 s e escalaria para a mesma equipe. A carga humana total fica igual (só a espera melhora) e, na retomada, o meio-aberto atrasa a volta da IA: o disjuntor pode aumentar a carga humana. H2 sai falsa por configuração da fila, não por medição | Política por fila, `ao_abrir_disjuntor` = `reter` ou `transbordar`, com `reter` como padrão nas filas AI first; E8 com a fila declarada; H2 reescrita por política (reter: menos carga humana; transbordar: menos espera) |
| R4 | alta | impl 8 (laço do distribuidor) | **Distribuidor com bloqueio de cabeça de fila.** `ORDER BY prioridade DESC ... LIMIT 20` sobre todas as filas: se as 20 primeiras são de uma equipe lotada, `SEM_CAPACIDADE` as deixa onde estão e o próximo ciclo pega as mesmas 20; as outras filas, com atendente livre, passam fome (justo no E8). `prioridade` é texto: em ordem decrescente, `media` vem antes de `baixa`, que vem antes de `alta`. A `prioridade` da fila (JSON da arq 12) e a "prioridade maior" da escala (princípio 3) não entram na ordem. As 20 conversas ficam numa transação: duas instâncias travam analistas em ordem diferente (deadlock no E9), uma exceção desfaz 20 decisões (contra o M5) e a mensagem do cliente numa dessas conversas espera o lote inteiro | Uma conversa por transação; seleção por fila e grupo que tenha capacidade (pular grupos lotados) ou `LIMIT` por fila; prioridade como inteiro; ordem por prioridade da fila, `origem = escalado`, prioridade da conversa e espera |
| R5 | alta | impl 7.1 (`transicionar`) | **`SEM_CAPACIDADE` depois de encerrar a atribuição.** `encerrar_atribuicao` roda antes de `tem_capacidade`; como a rejeição agora volta como resultado e quem chama confirma a auditoria (T16), a devolução `com_humano → com_ia` com a IA sem capacidade grava: conversa em `com_humano`, sem atribuição, prazos cancelados, `ativas` do analista decrementado. Ninguém a vê de novo (não está em `na_fila`); mensagens do cliente gravam com atribuição nula | Conferir a capacidade antes de encerrar, ou `SAVEPOINT` desfeito em qualquer resultado diferente de `APLICADO`. Teste: devolução com a IA no limite |
| R6 | média | arq 11.3 ("o timeout de 30 s vence antes das retentativas"); impl 7.3 (parágrafo depois de `atraso`); teste 13.2 ("escalada uma vez, pelo timeout") | T5 não foi propagado. Antes do envio, o prazo é 90 s; as retentativas esgotam entre 61,5 e 123 s: quem escala depende do jitter. E a folga fixa de 60 s ainda cobra do agente o atraso da plataforma: com a ordem por conversa e destino, a segunda mensagem espera atrás da primeira que está retentando e vence o prazo sem ter saído (resíduo do A3) | Resolvido por R1. Corrigir as três frases |
| R7 | média | impl 12 (fatia 1: "publicação direta"); arq 9 e 11.4 (broker único no Kafka) | A fatia 1 ainda é construída como a antiga ingênua: o núcleo produz e consome Kafka direto, e a fatia 2 joga isso fora para pôr broker e relay. Com o D-1, a tag `ingenua` é só marco; esse caminho é retrabalho num projeto atrasado e contradiz a fronteira da arq 9 | Decidir antes do passo 2: fatia 1 já com broker mínimo (webhook → Kafka, Kafka → `POST`), sem as regras da 11.4 |
| R8 | baixa | impl 4.2 ("responder uma mensagem cobre as anteriores") × arq 17 (perdida por mensagem enviada) | O contrato aceita agente que responde duas mensagens com uma; o juiz contaria a primeira como perdida. O mock responde 1:1, então o mês não é afetado | Juiz por cobertura (`seq` coberto), como o I1 |
| R9 | média | arq 11.9 ("abre depois de cerca de 10 escalas") | Certo, mas incompleto: as conversas que já estavam com a IA seguem escalando por timeout com o disjuntor aberto. Na meta do teste são ~3.500 (arq 3), e numa queda de 2 min quase todas mandam uma mensagem. O disjuntor protege só as conversas novas (seção 3) | Escrever na arq 11.9 e na previsão do E8 quantas escalas o disjuntor não evita |
| R10 | média | impl 7.1, 10 (`CAPACIDADE_HUMANO = 3`; e-mail encerra em 72 h) | A10 foi corrigido para a IA, não para o humano. Conversa com humano esperando o cliente ocupa vaga até a inatividade: no e-mail, até 72 h. Com 10 analistas simulados (30 vagas), poucos e-mails sem resposta do cliente lotam a equipe | Vaga humana conta só conversa em que o próximo passo é do analista, ou prazo de e-mail próprio para humano; declarar |
| R11 | média | impl 14 (E7) | E7 desligado mede quase nada: a janela entre commit e `POST` é de milissegundos; a ~58 eventos/s, um SIGKILL perde em média menos de 1 evento. Três repetições não separam as duas posições | 10 a 20 mortes por execução, ou atraso injetado entre commit e envio só no cenário; declarar a janela |
| R12 | média | arq 19 (fatia 9); impl 12, 14 | Sem roteiro de demonstração de 5 min nem gravação de reserva (pedidos na rodada 1, seção 9); "Recuperação" sem definição; sem formato dos resultados brutos nem script que gera as tabelas; semente só no k6, não no jitter do relay nem no mock | Roteiro fixado já; recuperação = tempo da volta da dependência até o I1 zerar; CSV bruto por execução e script das tabelas; sementes no `.env.example` |
| R13 | baixa | impl 14 (E2: "Previsto desligada: p95 maior") | Direção provavelmente trocada: sem outbox não há o laço de 100 ms nem as transações de reserva; a robusta deve ter p95 maior. A previsão deve mostrar o custo da proteção | Prever o custo e medir |
| R14 | baixa | impl 7.5 passo 5 | 500 repetido retenta dentro da partição: até ~2 min sem consumir 1/12 do tráfego, com timeouts de conversas alheias. Aceitável porque 500 agora é defeito, mas não está declarado | Declarar, ou mandar para `helpdesk.erros` já na primeira repetição |
| R15 | baixa | impl 12 (fatia 2), 7.1 | A capacidade da IA conta `timeout_agente` pendentes e a chave `TIMEOUT_ATIVO` está na fatia 2, mas `agendamentos` só nasce na fatia 3. Com o timeout desligado (E4, E5), a IA nunca fica sem capacidade | Capacidade da IA a partir da fatia 3; declarar a interação com a chave |
| R16 | baixa | impl 7.6, 14 | "Encerramento explícito" do k6 não tem API nem evento; o mock "resolve depois de N trocas" sem N; palavras de irritação no texto gerado escalam na parte 1, sem humanos | N ≥ 6 ou fim pelo mock; texto do k6 sem gatilho de escala |
| R17 | baixa | impl 14 (E4); arq 8 | E4 com duas chaves sem matriz: fencing desligado só aparece com timeout ligado. O diagrama da arq 8 omite o cliente como ator de `com_ia → escalada` (a impl 6 o tem) | Matriz 2 × 2 só com as células que fazem sentido; alinhar o diagrama |
| R18 | alta | arq 19 (marcos, plano de corte); diário | Resíduo do A14. O passo 1 da fatia 1 levou os primeiros dias; o marco da semana 1 (fatias 1 e 2) quase certamente cai, e a fatia 2 é a maior do plano. O plano de corte só age no marco da semana 3, e "Não sai" ainda inclui fatias 1 a 4, filas versionadas, distribuidor, handoff, disjuntor e README | Replanejar os marcos agora com a velocidade medida; tirar do "Não sai" o que pode nascer mínimo (configuração como editor JSON já na fatia 5; E9 1 × 2 desde o início) |
| R19 | média | impl 7.3, 7.5, 11 | Resíduo do A9. Workers do relay e concorrência do consumidor de volta do broker não estão dimensionados. No E2 (~100 eventos/s do agente), um consumidor que faz `POST` em série por ~10 ms fica perto de 100% de uso, e a latência interna (entrada → ack do broker) não vê o caminho de volta | Little por salto numa tabela; métrica de latência da volta (ack do Kafka → 200 do núcleo) |
| R20 | média | impl 14 ("6 mensagens de cliente com intervalo fixo") | O intervalo não tem valor, e ele define L. Com 5 s, a conversa dura ~30 s e L ≈ 250; para reproduzir os ~3.500 da arq 3, o intervalo precisa ser ~70 s. Disjuntor, capacidade e inatividade dão resultados diferentes conforme esse número | Fixar o intervalo a partir da arq 3 e escrever o L esperado na previsão |

---

## 3. Cálculo de apoio (R3 e R9)

Meta do teste (arq 3): 8,3 conversas novas/s, L ≈ 3.500 com a IA, uma mensagem de cliente a cada ~70 s por conversa (6 em 420 s). `ESPERA_MAX_RETIDA_S = 300`.

| Queda | Já com a IA, escalam por timeout | Novas no período | Novas que escalam pela espera máxima | Redução da carga humana com retenção | Com transbordo |
|---|---|---|---|---|---|
| 2 min | ~3.500 (quase todas escrevem em 120 s) | ~1.000 | 0 | ~1.000 de ~4.500 (~22%) | ~0 |
| 10 min | ~3.500 | ~5.000 | ~2.500 (de 5 a 10 min) | ~2.500 de ~8.500 (~30%) | ~0 |

Ordem de grandeza, não medida. H2 continua plausível com retenção, mas o efeito é de 20% a 30%; com transbordo, desaparece.

---

## 4. Notas

| Critério | Rodada 1 (D / V) | Auditoria (D / V) | Rodada 2 (D / V) | Por quê |
|---|---|---|---|---|
| Aderência e coerência | 7 / 6 | 6,5 / 6 | 7,5 / 7 | CLAUDE.md como ponteiros, escala pelo roteador, núcleo fora do Kafka, contrato sem 1:1. Perde por contradições novas (R3, R6, R7) |
| Filas configuráveis | 6 / 6 | 6 / 5 | 7 / 6 | Validação de valor, grupos, versão lida por roteamento, re-roteamento. O distribuidor escrito tem fome de fila e ordem por texto (R4); fatia 5 na semana 3 |
| Robustez da integração | 6 / 5 | 5 / 5 | 7 / 6,5 | A1 a A7, M3 a M5, N5 e N6 fechados no desenho. Restam R5 no caminho único de escrita e R6; a evidência depende de R1 e R2 |
| Handoff com contexto | 5 / 5 | 5 / 4 | 7 / 5,5 | Fila de escalas definida, contexto sob a trava, resumo atrasado anexado, fontes, reserva extrativa, timeout na devolução. Vaga humana presa por e-mail (R10); painel na semana 3 |
| Evidência de escalabilidade | 4 / 4 | 4 / 4 | 6 / 5,5 | Unidade, Little com a carga do teste, mock assíncrono, E9 em degraus. Sem Little por salto (R19) e com L do teste indefinido (R20) |
| Honestidade nas limitações | 7 / 8 | 6 / 8 | 7,5 / 8,5 | "Cerca de 70", "exatamente uma vez", Redpanda, Chatwoot, 420 s e rótulos corrigidos; previsão do E5 contra a própria versão. Perde por R9 e por previsões que o juiz não pode produzir (R1, R13) |
| Reprodutibilidade | 7 / 6 | 6 / 6 | 7 / 6,5 | Ablação com o mesmo código, semente no k6, juiz nas pontas, 3 repetições. Sem formato de resultado, script das tabelas e demais sementes (R12); README pendente |
| Demonstração | 5 / 4 | 5 / 4 | 5,5 / 5 | Leitura de 2 s simplifica a interface. Ainda sem roteiro nem gravação de reserva (R12) |
| **Geral** | **6,0 / 4,5** | **5,5 / 4,5** | **6,5 / 5,5** | Média das linhas: 6,8 / 6,3. O desenho fica abaixo da média porque H1 (E6, E7, E3b) e H2, a evidência principal, não podem sair como previstas do jeito que estão escritas (R1 a R3). A viabilidade fica abaixo porque o risco dominante, o cronograma, não foi replanejado (R18) |

O salto da auditoria para cá (+1,0 / +1,0) é real: 36 de 45 itens fechados sem nenhum bloqueante novo. Os cinco altos novos são do tipo "a correção certa encontrou outra peça": o retorno sem exceção (R5), os grupos de atendentes (R3), a ablação (R1, R2) e o laço do distribuidor recém-escrito (R4).

---

## 5. Se o usuário trouxer de volta um diferencial pequeno

**D1, persona por marca.** Custo: ~1 dia com o ritual (tabela versionada, duas personas semeadas, `dados.persona` já opcional no contrato, mock usando nome, saudação e idioma, teste). Mais barato: guardar a persona dentro da versão de regras, que já tem versão imutável, validação, rollback e `conversas.versao_regras`; sai por ~meio dia, e a auditoria da persona vem de graça.

| Quando | Desenho | Viabilidade | Efeito por critério |
|---|---|---|---|
| Agora (antes do marco da semana 3) | 6,5 → 6,6 | 5,5 → 5,25 | Aderência +0,5 (multi-marca visível); demonstração +0,5 (InfinitePay em PT e JIM em EN lado a lado); viabilidade cai porque compete com as fatias 1 a 4 |
| Depois do marco da semana 3, como primeiro bônus | 6,5 → 6,6 | sem efeito | Mesmo ganho, sem risco |

Recomendação: não agora. Pôr o D1 **antes** do D6 reduzido na ordem do bônus: custa um quinto, aparece na demonstração e não pede serviço novo. Com o mock respondendo texto fixo, a persona só aparece se o mock usar os campos dela; dizer isso na banca. Outro bônus barato pelo mesmo raciocínio: D3 mínimo (refazer os registros de decisão contra uma versão nova antes de ativar), porque o roteador já é puro; +0,5 em filas configuráveis.

---

## 6. O que ainda impede o 10

### 6.1 Correções possíveis, em ordem

1. **Prazo do agente só depois do ack** e esgotamento do relay como único caminho de escala antes do envio. Fecha R1 e R6 e devolve ao E6 e ao E7 desligados a perda que eles devem mostrar. Na mesma ficha: colunas "escaladas" e "espera até a 1ª resposta" na parte 1; escala vista na ponta.
2. **Deduplicação do `id_externo` pela inbox**, com a coluna sempre gravada (R2).
3. **Política do disjuntor por fila** (`reter` ou `transbordar`) e H2 reescrita por política, com os números da seção 3 (R3, R9).
4. **Distribuidor por item, por fila com capacidade, prioridade inteira** (R4).
5. **Capacidade antes de encerrar a atribuição** em `transicionar` (R5).
6. **Replanejar os marcos** com a velocidade medida e decidir a fatia 1 com broker mínimo (R18, R7).
7. **Modelo de carga fechado:** intervalo do k6 derivado de L, Little por salto, latência da volta (R20, R19).
8. **Roteiro de demonstração de 5 min**, gravação de reserva, CSV bruto e script das tabelas, sementes (R12).
9. E7 com várias mortes (R11); vaga humana que não conta espera do cliente (R10).
10. Baixas: R8, R13 a R17.

Com 1 a 5, o desenho vai a ~7,5. Com 6 a 8, a viabilidade vai a ~6,5 e a demonstração a ~7. O resto depende de execução: fatias entregues, tabelas preenchidas, README.

### 6.2 Limitações que nunca chegam a 10 (declarar)

- Agente mock com texto fixo: o "formato atual" da CloudWalk é presumido, e a qualidade de resposta e de resumo não é medida.
- Uma máquina: o E9 prova correção sob concorrência e o primeiro gargalo, não capacidade de produção.
- Redpanda de um nó em modo de desenvolvimento e Postgres sem réplica: sem falha de disco, de cluster ou de rede.
- Canais simulados: janela de 24 h do WhatsApp e encadeamento de e-mail ficam de fora.
- Analistas simulados: o lado humano do E8 é hipótese.
- A ablação desliga um mecanismo por vez: mede cada proteção isolada, não as interações (R15 é um exemplo).
- Premissas de volume extrapoladas de dado público de 2023; taxa de escala é hipótese.
- Dados sintéticos; triagem por regras; sem autenticação real nem RLS; marca fixa no contrato.
