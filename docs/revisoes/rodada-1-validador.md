# Revisão da arquitetura, rodada 1 (validador)

Data: 2026-11-19. Lido: `CLAUDE.md`, `docs/arquitetura.md` (arq), `docs/implementacao.md` (impl), `docs/referencias.md`, `docs/diferenciais.md`, `docs/diario.md` e o código da fatia 1 (`docker-compose.yml`, `nucleo/infra/modelos.py`, `migrations/versions/0001_fatia1_tabelas.py`, `contrato/`, `testes/test_contrato.py`). `pesquisa_diferenciais.md` serviu só para conferir fontes. Nenhum arquivo existente foi alterado.

Severidade: **bloqueante** = resolver antes de fechar a fatia atual; **alta** = resolver antes da fatia que usa o mecanismo, senão um critério da avaliação cai; **média**; **baixa**.

---

## 1. Notas

| Critério | Desenho | Viabilidade (1 pessoa, 1 mês) | Justificativa |
|---|---|---|---|
| Aderência à arquitetura de referência e coerência | 7 | 6 | Webhook + broker + Kafka, IA como atendente e filas no modelo Zendesk batem com o enunciado. Perde por incoerências internas: CLAUDE.md contradiz a arquitetura (A13), o núcleo fala direto com o Kafka (M4), inbox no broker contra o argumento ponta a ponta que o próprio texto cita (M4), regra 1:1 imposta a um agente de terceiros (A11) |
| Filas de fato configuráveis | 6 | 6 | Versão imutável em JSONB, validação, rollback e registro de decisão são o desenho certo. Falta o distribuidor (A8), o exemplo da própria arquitetura nunca casa, a semântica de `atendentes` é ambígua, o cache da versão ativa entre instâncias não existe e fila removida deixa conversa órfã (M2) |
| Robustez da integração (falhas, reentregas, picos) | 6 | 5 | Primitivas certas (outbox, inbox, fencing, lease, ack depois do efeito). Mas o pseudocódigo pronto entra em laço (A1), tem deadlock na corrida que o experimento provoca (A2), mede o timeout do ponto errado (A3), o disjuntor não faz o que o texto promete (A4), falta idempotência na entrada dos canais (A6) e o caminho de volta do broker reintroduz o travamento de partição que a 11.3 diz evitar (A7) |
| Handoff com contexto | 5 | 5 | Resumo, fontes e resumo de reserva são bons. Mas não está definido para onde vai a escala nem como o analista pega (A8), mensagem pode sumir do contexto (A5) e o resumo que chega atrasado é descartado (M3) |
| Evidência de escalabilidade | 4 | 4 | E9 é honesto sobre a máquina única, mas o modelo de carga não existe e cada salto é um consumidor em série que não chega a 100 msg/s (A9); a Lei de Little subestima as conversas abertas de 2 a 10 vezes (A10); falta índice no ponto que o próprio texto diz que serializa (M7) |
| Honestidade nas limitações | 7 | 8 | Acima da média: fontes marcadas pelo grau de conferência, a correção do uso do estudo do Alibaba, "não prova capacidade de produção". Perde por afirmações que não se sustentam: "cerca de 70" (A4), "exatamente uma vez" com canal externo e `acks=all` num Redpanda de um nó em modo dev (M6), Chatwoot desatualizado e 420 s sem fonte (M10) |
| Reprodutibilidade | 7 | 6 | Compose com versões fixadas, migrations, tag `ingenua`, 3 repetições. Falta o modelo de carga e semente dos geradores (A9); troca de imagem do Postgres com `down -v` no meio do projeto (L9); README vazio |
| Demonstração | 5 | 4 | A tela de acompanhamento na fatia 3 é a decisão certa. Não há roteiro de demo; painel do analista e configuração dependem de Next.js na semana 3 de um cronograma que já atrasou (A14) |

**Nota geral: desenho 6,0; viabilidade 4,5.** A viabilidade não é a média das linhas: o risco dominante é o escopo total não caber, e aí experimento e demonstração caem juntos.

O desenho acerta o diagnóstico (confiabilidade e estado, não throughput) e as primitivas. Não passa de 6 porque vários mecanismos descritos como prontos falham nos próprios cenários do experimento, e porque a comparação ingênua × robusta, que é a evidência principal, não mede o que promete (B1).

---

## 2. Problemas

Ordenados por severidade. `arq` = arquitetura.md, `impl` = implementacao.md.

| # | Sev. | Onde | Problema | Por que importa | Correção |
|---|---|---|---|---|---|
| B1 | bloqueante | arq 17; impl 9 (último parágrafo) e 14; CLAUDE.md decisão 13; migration 0001 | A linha de base ingênua não serve para a comparação prometida ("mesmas falhas nas duas"). (a) A ingênua publica direto no Kafka: não tem broker, então E6 (broker fora) não existe nela. (b) I4 na ingênua seria "reconstruído pelos eventos de auditoria", mas a tabela `eventos` só nasce na fatia 2. (c) A 0001 já tem `uq_mensagens_id_evento` e o mock usa `id_derivado`: no E3 a ingênua fica protegida por acaso ou o consumidor dela quebra no `IntegrityError` e trava a partição (vira perda, não duplicata); com `causado_por` nulo na fatia 1, o I3 fica cego na ingênua. (d) Sem timeout na ingênua, E4, E4b e E5 comparam coisas diferentes: na robusta da fatia 3 o timeout escala para humanos que só existem na fatia 6, e o I1 conta `escalada` como desfecho válido. No E5 (agente fora 60 s) a ingênua responde tudo quando o agente volta, com zero perda; a robusta escala milhares de conversas para ninguém | É a evidência que mais pesa. A tabela pode sair inválida ou contra a hipótese, e a banca vai perguntar por que a ingênua não tem broker. A decisão é agora: a tag `ingenua` sai no fim desta fatia | Antes da tag: (1) tabela cenário × versão com "não se aplica" onde couber (E6 só robusta, ou ingênua com broker repassador sem as regras da 11.4); (2) definir I1, I3 e I4 que valem nas duas versões (I4 da ingênua por comparação com a hora da mudança de estado gravada na própria conversa, ou sair da comparação); (3) decidir e declarar o `UNIQUE` de `id_evento` (proteção já presente na ingênua) e fazer o mock preencher `causado_por` desde a fatia 1; (4) na parte 1, colunas "escaladas" e "espera até a 1ª resposta"; (5) escrever no README que E5 pode favorecer a ingênua em tempo de resposta |
| A1 | alta | impl 7.3 passo 4; arq 11.3; arq 11.9 ("falha de integração aparece como timeout") | Ao esgotar as retentativas, o relay chama `transicionar(..., para="escalada")` sem `id_atribuicao`. Pela própria arq 11.9, o timeout de 30 s já escalou a conversa antes (as 8 tentativas levam de 61 a 123 s). `escalada → escalada` e `com_humano → escalada` não estão em `transicoes_permitidas`: `TransicaoInvalida`, rollback do lote inteiro do relay, a linha volta a `pendente` e repete para sempre, republicando em `helpdesk.erros` a cada volta e bloqueando a conversa pelo `NOT EXISTS`. Para destino `canal`, escalar porque o canal do cliente caiu não ajuda: a resposta do humano sai pelo mesmo canal | Laço infinito num mecanismo marcado como Decidido (16), disparado por qualquer queda de broker acima de ~1 min | Marcar `erro` em transação própria; escalar só se a atribuição do evento ainda for a atual (passar `id_atribuicao`, fencing) e tratar "já escalada" como nada a fazer; para `canal`, não escalar: alerta e reprocessamento. Teste: broker fora por 3 min |
| A2 | alta | impl 7.1 ("Ordem das travas ... evita deadlock"), 7.4, 7.8 ("não há corrida"); arq 11.2, 11.8 | A ordem declarada cobre só conversa → atendente. O agendador trava linhas de `agendamentos` (`FOR UPDATE SKIP LOCKED`, lote de 50) e depois a conversa. `transicionar` trava a conversa e depois atualiza `agendamentos` (`encerrar_atribuicao`, `prazos_de_inatividade`, cancelamento por resposta). Ciclo: resposta do agente ou mensagem do cliente no instante em que o prazo vence. É exatamente o teste da 13.2 ("chegando no mesmo instante em que o agendamento dispara") e o E4b | O Postgres aborta um dos dois: ou a mensagem do cliente recebe 500 (e o reenvio do canal vira duplicata, ver A6), ou o lote inteiro do agendador volta. A afirmação "não há corrida" está errada | Escrever a ordem completa: conversa → agendamento → atendente → disjuntor. Agendador lê os vencidos sem travar, depois por item `SELECT conversa FOR UPDATE SKIP LOCKED`, relê o agendamento sob a trava e age. Um item por transação |
| A3 | alta | impl 7.4 (timeout criado junto com a outbox); arq 11.5, 11.9, 11.10 ("Pico: Kafka absorve"); impl 14 E7 | O cronômetro do `timeout_agente` começa quando o evento entra na outbox. Todo atraso da própria plataforma (relay atrasado, broker fora, fila no Kafka num pico, núcleo reiniciando) vira "falha do agente": escala à toa e abre o disjuntor. No E7, ao reiniciar o núcleo, o agendador dispara de uma vez os prazos vencidos enquanto o broker ainda entrega as respostas represadas; as respostas chegam depois e o fencing as descarta | Contradiz "Kafka absorve o pico": acima de 30 s de fila, absorver é escalar. A robusta pode perder para a ingênua no E2 e no E7 em experiência do cliente, e o disjuntor abre com o agente saudável | Prazo começa no ack do broker (o relay grava `executar_em = enviado_em + T` na mesma transação que marca `enviado`); carência de `TIMEOUT_AGENTE_S` depois da subida do núcleo; declarar que fila no caminho de volta ainda conta contra o agente |
| A4 | alta | arq 11.9; impl 7.9, 14 E8; arq 17 H2 | (a) "Escalam no máximo ... cerca de 70" está errado: a janela é de 60 s e contém os sucessos de antes da queda; a taxa só passa de 50% uns 15 s depois do primeiro timeout. A 100 msg/s são centenas a mais de mil escalas, não 70 (seção 3). (b) No meio-aberto a contagem é de todos os `timeout_agente` da IA desde `mudou_em`, não só das sondas: as conversas retidas, prorrogadas a cada 30 s, contam. Na retomada, a fila represada no Kafka gera timeouts e o disjuntor oscila; sucessos das retidas fecham o disjuntor sem sonda nenhuma. (c) Sonda cancelada (`atribuicao_encerrada`) não conta: com `sondas_restantes = 0` e menos de 5 sucessos, fica em meio-aberto para sempre e a IA não recebe conversa nova. (d) E8 dura 5 min, igual a `ESPERA_MAX_RETIDA_S` (300 s): o resultado depende dessa coincidência. (e) H2 mede "fila de escalas", que o próprio disjuntor esvazia por construção, porque conversa nova vai direto `na_fila → com_humano` | O número que sustenta H2 é falso e o meio-aberto não faz o que o texto descreve | Janela por contagem (últimos 20 desfechos) ou janela curta; meio-aberto decide só pelas sondas (marcar o agendamento da sonda); sonda cancelada devolve a vaga ou reabre; E8 com quedas de 2 e 10 min; H2 sobre carga humana total (`na_fila` com humano + `escalada`) e espera p95 até a 1ª resposta |
| A5 | alta | impl 7.12 ("fora da transação"), 9 (I1); arq 13.2 | O contexto (últimas N mensagens) é montado antes da trava. Mensagem do cliente que chega com a conversa em `na_fila` entre `montar_contexto` e `transicionar` não entra no histórico de `conversa.atribuida` e não gera `mensagem.recebida` (não há atribuição). O agente nunca a vê. O I1 não acusa, porque qualquer mensagem da IA posterior satisfaz a consulta. `versao` não detecta, porque mensagem não sobe `versao`. Com o disjuntor aberto, o cliente retido escreve "tem alguém?" justamente nessa janela | Perda silenciosa de mensagem no caminho principal, invisível ao juiz do experimento | Ler o histórico dentro de `transicionar`, sob a trava (é SQL barato); só os trechos semânticos ficam fora. Contador `seq_mensagem` na conversa para detectar mudança. I1 passa a exigir que cada mensagem do cliente seja coberta por um evento enviado ao atendente |
| A6 | alta | arq 11.1; impl 7.2, 13.1 | Não há idempotência na entrada dos canais. WhatsApp e e-mail reenviam webhooks; cada reenvio vira mensagem nova, `mensagem.recebida` com id novo, resposta dobrada ao cliente. O I3 não vê (o `causado_por` é diferente). A lista de inboxes cobre núcleo, broker, mock e saída, mas não a entrada | Reentrega é requisito explícito (9) e é a duplicata mais comum de um help desk real | `id_externo` por canal (wamid, Message-ID) com `UNIQUE (canal, id_externo)` em `mensagens`; simuladores reenviam com o mesmo id; cenário E3b de reentrega pelo canal |
| A7 | alta | impl 7.5 passos 5 e 6; arq 11.3, 11.4 | Caminho de volta do broker: 5xx repetido vai para `helpdesk.erros` depois de 8 tentativas. Com o Postgres fora, o núcleo devolve 500 e as respostas do agente são descartadas para a fila de erros, contra "contrapressão, não perda". A retentativa (61 a 123 s) bloqueia a partição inteira, o travamento que a 11.3 diz evitar, e dispara timeouts de conversas que nada têm com o erro. Ninguém escala a conversa do evento descartado: só o timeout, com motivo errado | Falha de dependência vira descarte; um evento ruim derruba 1/12 do tráfego | 5xx e indisponibilidade são contrapressão (sem limite, com alerta); fila de erros só para 4xx e esquema inválido. Para não travar a partição: núcleo grava o evento cru numa tabela de entrada e responde 200, processando por conversa depois; ou tópico de retentativa. Evento de volta descartado audita e escala pela `id_atribuicao` |
| A8 | alta | arq 5 (princípio 3), 8, 12; impl 6, 8 | O distribuidor não tem algoritmo: quem dispara (evento ou laço), como conversas em `na_fila` voltam a ser tentadas quando libera capacidade, concorrência entre instâncias, ordem entre filas, como o analista "puxa". Até a fatia 5, `SemCapacidade` deixa a conversa parada sem retentativa. O princípio 3 diz que escalar "é voltar para o sistema de filas, com origem = escalado", mas a máquina de estados vai `escalada → com_humano` sem roteamento: `origem` nas condições fica sem uso e a "fila de escalas" não tem definição (ordem, filtro por marca e equipe, quem vê) | Requisito 3 (distribuição) e critério "handoff com contexto" dependem disso | Escrever o laço do distribuidor (`SKIP LOCKED` sobre `na_fila`, por prioridade e espera, com gatilho por NOTIFY ou intervalo curto) e a retentativa de `SemCapacidade`. Escala passa pelo roteador com `origem = escalado` (estado `escalada` = em fila humana), coerente com o princípio 3 |
| A9 | alta | impl 7.3, 7.5, 7.6, 10, 11, 14; arq 3, 16, 17 | O modelo de carga não existe e cada salto é um consumidor em série. Mock com `LATENCIA_MS = 800` num laço em série: 1,25 msg/s por consumidor; uma tarefa por partição: 15 msg/s com 12 partições; para 100 msg/s são ~80 em voo (Little), e com concorrência dentro da partição o commit de offset "só depois do efeito" exige controlar offsets contíguos, o que não está escrito. Relay em série: ~100 POST/s, mas cada mensagem do cliente gera duas linhas (broker e canal). O k6 não tem modelo de conversa: sem encerramento explícito, a conversa ocupa a IA por 20 min e `CAPACIDADE_IA = 2000` estoura em segundos; sem distribuidor até a fatia 5, a conversa fica parada. Ambíguo: "100 msg/s" é do cliente ou total (a seção 3 conta as duas pontas); E2 "rampa até 5x" sobre 100 dá 500 msg/s; latência interna tem duas definições (arq 16: até chegar ao agente; impl 11: até o ack do broker); intervalo de polling do relay não definido (entra no p95) | E1 falha por motivo alheio à robustez; H1 (p95 < 500 ms) e E9 ficam sem base. A decisão 2 ("não é throughput") vale para Postgres e Kafka, não para os consumidores com ack por mensagem que o próprio desenho impõe | Dimensionar cada salto por Little; mock assíncrono por chave com controle de offset; envios do relay em paralelo entre conversas; modelo de conversa no k6 (mensagens por conversa, intervalo, encerramento); definir a unidade de msg/s, o pico do E2 e uma só latência interna; relay acordado por NOTIFY ou polling curto declarado |
| A10 | alta | arq 3 (linha "Conversas simultâneas"); arq 11.8; impl 10 | A Lei de Little usa 420 s "divulgado do Claudio Walker" sem fonte em `referencias.md`. A fonte existe (release da CloudWalk), mas diz "respondidas em até sete minutos" para o atendimento da IA, contra 22 min do analista. Duração em sistema precisa incluir as escaladas (25% em 2023) e o tempo esperando o cliente até o encerramento (20 min no chat, 72 h no e-mail). L sobe de 1.200 para ~2.200 só com as escaladas e para ~3.500 com abandono no chat (seção 3); e-mail com 72 h domina tudo. Como a conversa esperando o cliente ocupa a capacidade, a IA (2.000) satura no cenário de estresse e as conversas vão para humanos: o AI first se inverte | "~1.200 conversas" sustenta a decisão 1, o disjuntor e o E9 | Citar a fonte e recalcular com tempo em sistema; capacidade da IA medida em mensagens em voo, não em conversas abertas, ou conversa esperando o cliente não ocupa capacidade |
| A11 | alta | impl 4.2 (regra da 1.0), 7.4 (cancelamento por `causado_por` igual), 9 (I3) | "Cada `mensagem.recebida` gera no máximo uma `mensagem.enviada`" e o cancelamento do timeout por `causado_por` exato impõem comportamento a um agente que o projeto não controla. Agente que responde duas mensagens seguidas com uma (comum) faz a primeira estourar o prazo e escalar. Agente que manda "vou verificar" e depois a resposta vira duplicata no I3. Exige também `id_derivado` do agente real | O enunciado pede integrar "no formato atual"; o juiz do experimento conta como duplicata o que é comportamento legítimo | Cancelar os prazos pendentes da atribuição até a mensagem coberta (`causado_por` aponta a última mensagem respondida); permitir várias `mensagem.enviada` com `sequencia`; I3 por conteúdo repetido com ids diferentes ou por `(causado_por, sequencia)`; declarar o determinismo de id como requisito do contrato |
| A12 | alta | impl 9 (I1, I3, I4), 7.1; arq 11.6 | O juiz mede errado. I4 é tautológico: `transicionar` grava `mensagem.id_atribuicao = c.id_atribuicao_atual`, então a mensagem sempre está "dentro" da atribuição e a checagem nunca falha na robusta. I1 acusa como perdida conversa em `na_fila` esperando humano (fila só humana lotada) e aceita como atendida a mensagem que nenhuma resposta tratou (A5). `criada_em = now()` é a hora de início da transação: mensagens da mesma conversa podem gravar fora da ordem de commit, o que afeta I1 e o histórico mostrado ao agente | As colunas "Perdidas" e "Fora de dono" da tabela principal não significam o que dizem | I4 compara a atribuição que o agente declarou no evento com a atual no momento da gravação (gravar as duas); I1 separa "sem desfecho" de "esperando humano"; ordem por `seq_mensagem` sob a trava ou `clock_timestamp()` |
| A13 | alta | CLAUDE.md ("Decisões já tomadas" 6, "Plano de construção"); arq 19, 20 | O CLAUDE.md, que o agente de código lê primeiro, contradiz a arquitetura que ele mesmo chama de fonte da verdade: plano antigo (4 = Filas, 7 = Experimento) contra o novo (4 = Experimento parte 1, 5 = Filas); decisão 6 dá envelhecimento como decidido e a arq 20 o põe em Evolução; a arq 20 afirma "status alinhados ao CLAUDE.md" | O próximo agente pode construir na ordem errada; na banca, dois documentos dizem coisas diferentes | Atualizar o CLAUDE.md (é do usuário: propor o texto e pedir aval), deixando nele só ponteiros e o que muda o comportamento do agente |
| A14 | alta | arq 19 (marcos e plano de corte); diario | Escopo de dois a três meses: núcleo com 11 módulos, broker, mock com 5 modos, serviço de embeddings, reconciliador, Next.js com 4 telas e SSE, 3 simuladores de canal, k6, injeção de falhas, analistas simulados, conjunto rotulado de 100 consultas, 12 cenários × 3 repetições, README. No dia 3 está no passo 1 de 4 da fatia 1; o marco da semana 1 pede fatias 1 e 2 com o ritual de uma parte por turno. O plano de corte mantém detector e casos parecidos como contingência, quando deveriam sair já, e a lista "Não sai" é longa | Risco real de não ter demonstração nem experimento completo | Cortar já o que está na seção 8; replanejar marcos com a velocidade medida da fatia 1 |
| M1 | média | `contrato/envelope.py` linhas 30 e 34; impl 4.1, 15; arq 10; CLAUDE.md e arq 10 (exemplo) | Leitor tolerante só no papel. `versao: Literal["1.0"]` e `tipo: Literal[...]` recusam 1.1 e tipo novo, contra o comentário da linha 30 e a regra "tipo novo é anunciado numa versão menor". A correção planejada (aceitar "1.0" e "1.1") troca uma lista fechada por outra: a 1.2 do D5 quebra de novo. Tipo desconhecido vai para a fila de erros. `dados` é `dict[str, Any]`, sem o JSON Schema por tipo da decisão 7. O exemplo de envelope (`evt_8f2a...`, `conv_123`, `atr_41`) é recusado pelo código, que exige UUID | Contradição entre doc e código já apontada no próprio doc, mas com correção insuficiente | Como o contrato ainda não tem consumidor, pôr `agente.processando` já na 1.0 e eliminar a 1.1; aceitar `^1\.\d+$`; tipo desconhecido é auditado e confirmado, não vira erro; corrigir os exemplos |
| M2 | média | arq 12 (JSON da fila); impl 5.2, 8 | O exemplo da arquitetura nunca casa: `"valor": "JIM"` contra a marca `jim` do contrato, e a validação só confere campo e operador, não valor. Id de fila é slug (`fila_jim_credito`) no JSON e no registro de decisão, mas `uuid` em `conversas.id_fila` e `atribuicoes.id_fila`. `atendentes` mistura atendente e equipe (`time_credito_us`) sem definir a semântica; o Zendesk roteia para grupo primário e secundário. Não se diz como cada instância lê a versão ativa ("ativar é atômico" só vale lendo o banco a cada roteamento ou com invalidação). Conversa em `na_fila` de fila removida fica órfã. Sem envelhecimento, fila de baixa prioridade passa fome quando os humanos lotam (E8); e o envelhecimento não precisa do agendador, cabe no `ORDER BY` | "Filas de fato configuráveis" é critério da avaliação | Validar valores contra o domínio; id de fila em texto (ou uuid nos exemplos); `atendentes` = lista ordenada de grupos (equipe ou IA); ler a versão ativa por roteamento; ao ativar, re-rotear o que está na fila removida; envelhecimento como expressão no `ORDER BY` |
| M3 | média | impl 7.1; arq 10, 11.2 | `auditar("transicao_invalida")` seguido de `raise` é desfeito pelo rollback: o teste 13.1 "rejeitada e auditada" não passa como escrito (o mesmo vale para `SemCapacidade`). O fencing descarta `acao.executada` atrasada, mas a ação já aconteceu no mundo real; a auditoria guarda só "descartado", sem o conteúdo. `conversa.escalada` atrasada leva junto o resumo de que o analista precisaria. `eventos` "só inserção" sem trigger nem permissão que impeça `UPDATE` | Requisito 7 (auditar cada decisão) falha nos casos que mais importam | Auditar rejeição em transação própria ou devolver resultado sem exceção; `acao.executada` sempre auditada com conteúdo e marca "fora da atribuição"; resumo atrasado anexado à escala; trigger que recusa `UPDATE`/`DELETE` em `eventos` |
| M4 | média | impl 3, 7.2, 7.3; arq 11.1 | O núcleo publica direto em `helpdesk.erros`, furando a fronteira "só o broker fala com o Kafka"; com o Kafka fora, a publicação falha dentro da transação do relay. A arq 11.1 dá inbox ao broker; a impl 7.2 não; o broker não tem banco; e Saltzer, citado logo abaixo, diz que a deduplicação completa é nas pontas | Incoerência entre documentos e com a base citada | `outbox.status = 'erro'` é a fila de erros do núcleo, com endpoint de reprocessamento; broker sem inbox, deduplicação no mock e no núcleo |
| M5 | média | impl 7.3, 7.4 | Relay e agendador processam 50 itens numa transação. Uma exceção ou um deadlock desfaz o lote e repete os outros 49 (reenvio, reexecução). O relay faz HTTP dentro da transação: com o broker lento, 50 × timeout de transação aberta | Amplifica cada falha pontual | Um item por transação (ou `SAVEPOINT`); reserva curta (`status = 'enviando'` com prazo) e envio fora da transação |
| M6 | média | arq 11 (abertura), 11.4; `docker-compose.yml` (`--mode=dev-container`) | "Efeito de exatamente uma vez" só vale onde o receptor deduplica: WhatsApp e e-mail reais e o agente real não têm inbox nossa (é pelo menos uma vez). O Redpanda em modo dev ignora fsync e confirma antes de gravar em disco, e tem um nó (fator de replicação 1): `acks=all` não garante durabilidade | Afirmação de garantia que o ambiente não entrega | Declarar as duas coisas nas limitações; não matar o Redpanda nos cenários ou usar modo produção para eles |
| M7 | média | impl 5.2, 7.1, 9 | `conversas_ativas` conta atribuições sem índice `(id_atendente) WHERE fim IS NULL`, sob a trava da linha da IA, que toda atribuição pega: varredura crescente sob trava global. Reconciliador a cada 30 s varre `mensagens` inteira (I3 sem índice em `causado_por`, I1, I7) durante a carga e mexe no p95 que está medindo. `outbox` e `agendamentos` crescem sem limpeza | O ponto que o texto já chama de serialização fica pior que o necessário | Índice parcial ou contador `ativas` na linha do atendente atualizado sob a mesma trava; consultas do reconciliador por janela de tempo, com índice; limpeza periódica |
| M8 | média | arq 20 | Decisões 8, 9, 13 a 19 e parte da 12 passaram a Decidida sem aval. Há base textual (o CLAUDE.md, no commit `b7c86ac`, já as listava como tomadas, enquanto a arquitetura do mesmo commit dizia Proposta), mas o procedimento do projeto é "você propõe, eu valido": o certo era apontar a contradição e perguntar. Maturidade técnica de cada uma na seção 7 | Status falso em documento de banca | Voltar 16 e a segunda metade da 17 para Proposta; decidir as demais com as correções da seção 7, com aval |
| M9 | média | todos os docs | Inchaço: arq 593 → 954 linhas (+61%), impl 616 → 1.159 (+88%), referências 191 → 324 (+70%). Cerca de 40% sai sem perder decisão (seção 5) | O CLAUDE.md pede documentação enxuta; a banca não lê 3.000 linhas | Seção 5 |
| M10 | média | arq 3, 6, 10, 11.5, 13.3; referencias | Evidência mais fraca que o uso: Chatwoot "não refaz webhooks e joga para humano" está desatualizado e vem de documentação de terceiro; 420 s sem fonte e com outro significado (A10); Overeem trata de sistemas *event sourced*, não de contratos de mensageria em geral, e o resumo não recomenda ordem de táticas; Dai sustenta que valor errado e checagem ausente dominam, não que um agendador único os reduz (inferência); COTA é classificação e seleção de resposta, não recuperação de casos parecidos; MTEB-PT marcado `[revisado]` com leitura da versão arXiv. Detalhe na seção 6 | "Onde melhoramos" sobre o Chatwoot é pergunta certa de banca | Requalificar cada frase como na seção 6 |
| M11 | média | arq 13.5; impl 14 (E10, E11) | Qwen3-Embedding-0.6B em CPU dificilmente acompanha ~50 mensagens de cliente/s no worker; o critério da 13.5 olha a latência da consulta, não a vazão do worker contra a taxa de entrada. Pendência acumulando vira estado permanente durante o E1 | Memória semântica degradada justamente na carga | Incluir vazão do worker no critério; e5-small como padrão se a memória semântica ficar |
| L1 | baixa | arq 2, 13, 19 | Numeração de requisitos própria: na arq, memória é o requisito 9; no enunciado, é o 8 | Confunde na banca | Usar a numeração do enunciado |
| L2 | baixa | arq 12.1; impl 9 (I8) | I8 refaz a mesma função pura com as mesmas entradas: só pega adulteração do log ou não determinismo | Invariante de pouco valor | Teste unitário, não invariante |
| L3 | baixa | arq 9 ("O reconciliador só lê"); impl 9 | O reconciliador grava `violacoes` e auditoria; na ingênua essas tabelas não existem | Detalhe, mas afeta B1 | Reconciliador com banco ou arquivo próprio |
| L4 | baixa | `contrato/envelope.py` (`Marca`); impl 5.3, 7.13 | Marca como `Literal` no contrato, literal SQL e um índice HNSW por marca: terceira marca exige deploy e DDL | "Regras são dados" vale para filas, não para marcas | Declarar |
| L5 | baixa | `nucleo/infra/modelos.py`; migration 0001 | `estado` sem `CHECK`; `atualizada_em` nunca atualizado | Integridade no banco (o próprio texto cita Bailis) | `CHECK` com os seis estados; atualizar em `transicionar` |
| L6 | baixa | impl 7.4 | `pg_try_advisory_lock` é de sessão: com pool de conexões, a trava pode ficar presa a uma conexão devolvida | Laço periódico parado ou duplicado | `pg_try_advisory_xact_lock` |
| L7 | baixa | arq 8, impl 6 | Reabertura não re-roteia nem limpa `motivo_encerramento` e `resolvida_em`; `conversa.devolvida` não cria timeout | Métrica e prazo errados em caso de canto | Re-rotear na reabertura; limpar os campos; timeout também na devolução |
| L8 | baixa | `README.md` | Vazio (0 bytes) | Reprodutibilidade começa agora | Levar para o README os comandos de verificação do diário |
| L9 | baixa | `docker-compose.yml`; impl 2; arq 9 e 15 | `postgres:16-alpine` não tem pgvector. A impl 2 reconhece e prevê trocar na fatia 7 com `docker compose down -v`; o diagrama da arq 9 já desenha "PostgreSQL + pgvector" | Recriar o volume no meio dos experimentos | Trocar agora para `pgvector/pgvector:pg16` (mesmo Postgres 16), a custo zero |

**Contradições, índice rápido:** doc × código: M1 (versão e tipo, ids dos exemplos), M2 (id de fila), L9 (imagem sem pgvector, já reconhecida no doc). Doc × doc: A13 (CLAUDE.md × arq), M4 (inbox do broker), A9 (duas latências, pico do E2), L1 (numeração), arq 5 princípio 3 × arq 8 (A8), arq 11.8 "não há corrida" × impl 7.4 (A2), arq 11.10 "Kafka absorve" × timeout de 30 s (A3).

---

## 3. Cálculos de apoio

**Disjuntor (A4).** Janela de 60 s, taxa de 50%. Seja *r* a taxa de mensagens de cliente em conversas com a IA. O agente cai em *t0*; os primeiros timeouts saem em *t0 + 30*. Em *t0 + 30 + x*, a janela tem *r(30 − x)* sucessos de antes da queda e até *r·x* falhas. A taxa passa de 50% em *x ≈ 15 s*. Escalas antes de abrir ≈ *15r + 50* (o lote): com *r* = 20/s, ~350; com *r* = 100/s, ~1.550, mais do que os "~1.200 sem disjuntor" do mesmo parágrafo. "Cerca de 70" só valeria com janela por contagem (últimos 20 desfechos).

**Little (A10).** Chegadas no pico de estresse: 2,9 conversas/s. Com 75% resolvidas pela IA em 420 s e 25% escaladas (420 s de IA + 1.320 s de humano, os 22 min da mesma fonte): L = 2,9 × (0,75 × 420 + 0,25 × 1.740) ≈ 2.200. Se metade das resolvidas pela IA terminar por silêncio do cliente (+1.200 s até o encerramento no chat): ≈ 3.500. Uma fração pequena de e-mails abandonados com encerramento em 72 h já soma dezenas de milhares de conversas abertas. Os percentuais de abandono são ilustrativos; o ponto é que o tempo em sistema, não o tempo de atendimento, define L.

**Vazão por salto (A9).** Little por salto: em voo = taxa × latência. Mock: 100 × 0,8 s = 80 em voo; laço em série dá 1. Broker de volta: 100 × ~20 ms = 2 em voo; laço em série por consumidor dá ~50 msg/s. Relay: 2 linhas por mensagem do cliente (broker e canal) × 100 = 200 POST/s; em série, ~100.

---

## 4. Riscos que a banca vai explorar

1. "Por que a ingênua não tem broker, se o experimento derruba o broker?" (B1)
2. "No E5 a ingênua respondeu todo mundo e a robusta mandou mil conversas para humanos que não existiam. Quem ganhou?" (B1, A3)
3. "Esse disjuntor abre com quantas escalas, de fato?" (A4)
4. "O WhatsApp reenviou o webhook. O cliente recebe duas respostas?" (A6)
5. "Se o Postgres cair, as respostas do agente vão para onde?" (A7)

---

## 5. Inchaço: o que pode sair sem perder decisão

**arquitetura.md (~380 linhas a menos)**
- Status em três lugares (título "(proposta)", parágrafo-ponte no início das seções 8, 9, 11, 15, 17 e tabela 20). Deixar só a tabela 20.
- Blocos "Base" de 11.1 a 11.9, 12, 13 repetem `referencias.md` quase palavra por palavra. Trocar por citação curta (autor, ano) e manter o texto em `referencias.md`.
- Parâmetros numéricos de 11.7, 11.8, 11.9, 13.1, 13.2, 13.4, 13.7 duplicam a impl 10. Apontar para a tabela de configuração.
- Seção 13 (~110 linhas) para um diferencial: manter 13.1 (os três blocos) e cinco linhas de 13.2; mover 13.3 a 13.7 para `diferenciais.md` (D6). A tabela de modelos (13.5) aparece em três lugares (arq 13.5, impl 14 E10, impl 15).
- Diagramas de sequência de 11.7 e 13.2 são implementação; os de 7.1 e 11.2 bastam.
- Seção 16 duplica impl 11 e 14; seção 17.1 duplica impl 3 e 14; seção 18 duplica `diferenciais.md`.
- Seção 19, "Por que mudou": histórico, vai para o diário.

**implementacao.md (~250 linhas a menos)**
- 5.3, 7.11 a 7.14, `incidentes`, E10 a E12b e as variáveis de memória: anexo do D6, fora do guia principal enquanto não houver aval para construir.
- 4.1 "Ajuste no código quando a 1.1 entrar" repete a linha da seção 15; some se a 1.1 for eliminada (M1).
- 4.2 "O campo `resumo_anterior` ... sai": histórico.
- Parágrafo da imagem do Postgres em 2: some se a imagem for trocada já (L9).

**referencias.md (~100 linhas a menos)**
- Notas de processo ("O link anterior ... 404", "A página não abriu na conferência ...") viram um rótulo: conferido no texto, no resumo ou em fonte secundária.
- Seções 2 e 5 (τ-bench, Cemri, LLMCompiler, RouteLLM, PagedAttention) não sustentam decisão do mês; seção 11 (indicados, não estudados) também. Cortar ou juntar numa linha "leitura".

**CLAUDE.md** (do usuário; só propor): envelope, contrato, plano de fatias e decisões duplicam a arquitetura e já divergiram (A13). Deixar ponteiros, o ritual e as regras de trabalho.

---

## 6. Evidência conferida na web (2026-11-19)

| Citação | Uso | Resultado |
|---|---|---|
| CloudWalk, release "Generative AI brings $20 million return" | Volume (decisão 1) | Confere: "75% of all services provided by InfinitePay in 2023" e "about 2.6 million requests". A mesma página traz "more than 1.2 million customers" e "answered within seven minutes" contra 22 min do analista: é a fonte do 420 s, não citada para isso, e "em até 7 min" não é duração da conversa aberta |
| Let's Money, 2026 | Volume de estresse | Confere 6,3 mi de clientes e "dobrou em um ano"; diz que a IA resolve mais de 90% (dado da empresa). Não traz 1,2 mi de 2023 (isso vem da fonte acima) |
| Overeem et al., JSS 2021 (arXiv 2104.01146) | Evolução do contrato (decisão 34) | 19 sistemas, 25 engenheiros e as cinco táticas conferem. São sistemas *event sourced*; o texto da arq diz "orientados a eventos". O resumo não recomenda ordem de táticas (o doc já admite fonte secundária) |
| Huang et al., OSDI 2022 | Disjuntor | Confere: 22 falhas metaestáveis, 11 organizações, ao menos 4 de 15 grandes quedas da AWS |
| Dai et al., IC2E 2018 | Agendador único, prazo renovável | Confere pelos slides: 156 bugs em 11 sistemas; valor de timeout mal usado (47%) e checagem ausente (31%) dominam. Os bugs são de comunicação entre componentes; "um ponto só para prazos reduz esses erros" é inferência do redator |
| Levin (Recall.ai), 2025 | Risco do NOTIFY | Confere a trava global no commit. O relato é de "dezenas de milhares" de escritores simultâneos e o post diz que um commit removeu o gargalo no core do Postgres. Nesta escala o risco é baixo |
| Chatwoot, `lib/webhooks/trigger.rb` (branch develop) | "Onde melhoramos" (arq 6) | Desatualizado: webhook de agent bot com 429 ou 500 levanta erro marcado como retentável, e há opção por conta (`keep_pending_on_bot_failure`) que impede abrir a conversa na falha. Não confirmei quantas tentativas o job faz. A fonte usada é documentação de um fork de terceiro (mintlify, Merkurcode/nauto-console) |
| Redpanda, `rpk redpanda mode` / deploy para desenvolvimento | `acks=all` (arq 11.4) | Modo dev ignora fsync e confirma antes de gravar em disco (M6) |
| Okamura et al., MTEB-PT (arXiv 2607.04071) | Modelo de embedding | Aceito no BRACIS 2026. Tabela 3 confere: recuperação 78,9 / 70,2 / 17,6 / 67,3 / 58,0 e reranking 85,8 do Qwen3. Rótulo `[revisado]` com leitura da versão arXiv: rebaixar para "preprint aceito" |
| Wang et al., Alibaba (arXiv 2605.14830) | Gatilho por sentimento (arq 12) | Confere com o uso atual: experimento de campo randomizado; intervenção menos eficaz nas escalas emocionais disparadas por algoritmo; intervir cedo é essencial. O resumo não traz o número de conversas (não conferi o 680.676) |
| Zendesk, ordem das filas (6831121209498) | Modelo de filas | Confere "primeira fila que casa". O artigo não descreve fila padrão; a fila roteia para grupo primário e secundário, não para lista de atendentes (base de M2) |
| pgvector, README | Memória | Confere: filtro de 10% com `ef_search` 40 devolve ~4; busca iterativa desde 0.8.0; 4 × d + 8 bytes. A tag de exemplo é `pg18-trixie`, com `0.8.7-pg18-trixie` listada |
| Molino et al., COTA (arXiv 1807.01337) | Casos parecidos (arq 13.3) | Confere −10% no tempo de resolução sem perda de satisfação. COTA classifica tickets e seleciona respostas; não recupera casos parecidos. Uso como base de 13.3 é extrapolação |

---

## 7. Decisões promovidas a Decidida: maturidade

| # | Decisão | Madura? | Por quê |
|---|---|---|---|
| 8 | Monólito modular; broker e mock fora | Sim | Igual ao CLAUDE.md 9. Corrigir M4 (núcleo publicando no Kafka) sem mudar a decisão |
| 9 | Outbox + idempotência + fila de erros | Princípio, sim | Os detalhes estão nas linhas 14, 16 e 17 |
| 12 | Experimento comparativo | Princípio, sim; "mesmas falhas nas duas", não | B1: E6 sem broker na ingênua, I4 sem auditoria, timeout ausente |
| 13 | Envelope com `id_atribuicao` e `causado_por` | Sim | Já no código e testado |
| 14 | Inbox por consumidor e id determinístico | Parcial | Falta a entrada dos canais (A6); inbox no broker contradiz a impl 7.2 e o argumento ponta a ponta (M4); id determinístico do agente real é requisito do contrato, não garantia (A11) |
| 15 | `transicionar` com trava, transições e fencing | Princípio, sim; detalhe, não | Ordem de travas incompleta (A2); auditoria de rejeição some no rollback e fencing não pode apagar `acao.executada` (M3) |
| 16 | Ordem na outbox; retentativa limitada; fila de erros escala | Não | Laço com `TransicaoInvalida` e escala por falha de canal (A1); cronômetro (A3). Voltar para Proposta |
| 17 | Broker confirma só depois do Kafka e do núcleo | Primeira metade, sim; segunda, não | 5xx vira descarte e a retentativa trava a partição (A7) |
| 18 | Agendador único | Sim, com correção | Ordem de travas e um item por transação (A2, M5) |
| 19 | Reconciliador | Princípio, sim; invariantes, não | I1 e I4 medem errado (A12); I8 trivial (L2) |

---

## 8. Cortes para caber no mês

**Cortar já** (vira evolução declarada no README):
1. Detector de incidente e casos parecidos (13.3, 13.4, 7.13, 7.14, E12, E12b).
2. Comparação de três modelos de embedding. Se a memória semântica sobreviver: e5-small contra recência, e nada mais.
3. SSE com LISTEN/NOTIFY: trocar por leitura periódica de 2 s no painel. Some a thread de LISTEN, a fila por navegador e o risco do NOTIFY no E9.
4. Contrato 1.1 como versão separada: `agente.processando` entra na 1.0.
5. I8 e inbox do broker.
6. D1 a D5 fora do mês, sem exceção.

**Simplificar**
- Disjuntor: janela por contagem, meio-aberto só pelas sondas, retenção = "não distribui para a IA + espera máxima". A prorrogação de quem já está com a IA só se sobrar tempo.
- Inatividade: um prazo por canal, sem aviso, se apertar.
- E9: 1 × 2 instâncias se faltar tempo.

**Não cortar** (é onde está a nota): outbox, inbox na entrada e nas pontas, `transicionar` com fencing, agendador com timeout, reconciliador I1 a I6 corrigidos, filas versionadas com editor JSON, distribuidor, handoff com resumo e fila de escalas, memória operacional (perfil e últimas N, que já atendem o requisito 8), experimento parte 1, roteiro de demo.

---

## 9. O que impede a nota 10

**Aderência e coerência**
1. CLAUDE.md alinhado à arquitetura (A13).
2. Escala volta às filas com `origem = escalado` (A8).
3. Contrato que não impõe 1:1 nem id determinístico como garantia (A11).
4. Núcleo sem Kafka direto; broker sem inbox (M4).

**Filas configuráveis**
1. Distribuidor escrito e testado sob concorrência (A8).
2. Itens de M2: valores validados, ids coerentes, `atendentes` como grupos, versão ativa lida por roteamento, re-roteamento de órfãs, envelhecimento no `ORDER BY`.
3. Demonstrar troca de regra ao vivo, com efeito na conversa seguinte e decisão registrada.

**Robustez**
1. A1, A2, A3, A4, A6, A7, M3 e M5 corrigidos.
2. Teste para cada caminho de erro novo: deadlock forçado, evento ruim no caminho de volta, reentrega pelo canal, reinício do núcleo com respostas represadas, broker fora por 3 min.
3. E5, E6 e E7 publicados por versão, com escaladas e espera até a 1ª resposta.

**Handoff**
1. Fila de escalas definida: ordem, filtro por marca e equipe, quem vê (A8).
2. Contexto lido sob a trava (A5); resumo atrasado anexado (M3); devolução com timeout (L7).
3. Medir tempo até o handoff e se o analista teve o histórico completo.

**Escalabilidade**
1. Modelo de carga e consumidores dimensionados por Little (A9).
2. L recalculado e capacidade da IA redefinida (A10); índices de M7.
3. E9 em degraus com o gargalo identificado por medição (`pg_stat_activity`, atraso do consumidor).

**Honestidade**
1. Corrigir "cerca de 70", "exatamente uma vez", `acks=all`, Chatwoot e 420 s (A4, M6, M10, A10).
2. Tabela de limitações no README ligada a cada hipótese.
3. Publicar resultado contrário se vier (E5 e E7 podem favorecer a ingênua em tempo de resposta).

**Reprodutibilidade**
1. Um comando sobe tudo e roda um cenário; semente fixa no gerador sintético e no jitter; resultados brutos em CSV com o script que gera as tabelas; tags git das duas versões.
2. Imagem `pgvector/pgvector:pg16` já, em vez de recriar o volume na fatia 7 (L9).

**Demonstração**
1. Roteiro de 5 min fixado agora: cliente escreve, IA responde, escala, analista assume e devolve; supervisor troca regra; agente derrubado com disjuntor; reconciliador zerado.
2. Tela mínima por leitura periódica antes de qualquer SSE; dados semeados; gravação de reserva.


---

## 10. Limitações que nunca chegam a 10 (declarar, não corrigir)

- O agente é mock: o "formato atual" da CloudWalk é presumido, e a qualidade do resumo e das respostas não é medida.
- Uma máquina: E9 prova correção sob concorrência, não capacidade de produção.
- Redpanda de um nó em modo dev, Postgres único sem réplica: sem teste de falha de disco, de cluster Kafka ou de partição de rede.
- Canais simulados: semântica real de WhatsApp (janela de 24 h, reenvio) e de e-mail (encadeamento) fica de fora.
- Analistas simulados: os números do lado humano no E8 são hipóteses.
- A versão ingênua é construída por nós: representa um sistema sem as proteções, não o help desk atual.
- Dados sintéticos: precisão da memória superestimada; triagem por regras sobre linguagem regular.
- Sem autenticação real nem RLS.

---

## Fontes consultadas

- https://www.cloudwalk.io/newsroom-releases/generative-ai-brings-20-million-return-for-brazilian-fintech-cloudwalk
- https://www.letsmoney.com.br/ia/cloudwalk-receita-us-1-7-bi-ia/
- https://arxiv.org/abs/2104.01146
- https://www.usenix.org/conference/osdi22/presentation/huang-lexiang
- https://tingdai.github.io/files/understanding_IC2E18_slides.pdf
- https://recall.ai/blog/postgres-listen-notify-does-not-scale
- https://raw.githubusercontent.com/chatwoot/chatwoot/develop/lib/webhooks/trigger.rb
- https://docs.redpanda.com/current/reference/rpk/rpk-redpanda/rpk-redpanda-mode/
- https://arxiv.org/abs/2607.04071 e https://arxiv.org/html/2607.04071
- https://arxiv.org/abs/2605.14830
- https://support.zendesk.com/hc/en-us/articles/6831121209498
- https://github.com/pgvector/pgvector
- https://arxiv.org/abs/1807.01337
