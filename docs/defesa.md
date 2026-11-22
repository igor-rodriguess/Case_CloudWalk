# Guia de defesa para a banca

Guia de estudo para defender a arquitetura e o backend. Tudo aqui vem de `README.md`, `docs/arquitetura.md` (arq), `docs/implementacao.md` (impl), `docs/referencias.md`, `docs/diario.md`, `docs/revisoes/rodada-4-validador.md` e do código. Onde há dúvida ou divergência entre documento e código, está dito.

Estado em 2026-11-22: o experimento está rodando e o README ainda tem `RESULTADOS_AQUI`. Nenhum resultado medido aparece neste guia; onde a fala depende do resultado, está marcado **[preencher com o resultado]**.

Regra para a banca: número só com fonte. Os números de artigos da seção 6 de `referencias.md` (Bailis, Yuan, Saltzer etc.) foram conferidos **só pelo resumo**, e o próprio arquivo pede para conferir no texto completo antes da banca. Se não der tempo, diga "pelo resumo do artigo".

---

## 1. O pitch de 1 minuto

**Problema.** A CloudWalk (InfinitePay no Brasil, JIM nos EUA) já tem um agente de IA que atende lojistas de ponta a ponta, ligado ao help desk por webhook, broker e Kafka. O help desk é de terceiros: lento, com defeitos recorrentes e sem a estrutura multi-marca e multi-equipe da operação (arq 1).

**O insight.** O volume é baixo. Em 2023 a IA fez cerca de 2,6 milhões de atendimentos, 75% do total (release da CloudWalk, `[mercado]`), o que dá perto de 9,5 mil atendimentos por dia. Mesmo no cenário de estresse (50 mil por dia, premissa), o pico concentrado é cerca de 70 msg/s (arq 3), pouco para Postgres e Kafka. O difícil é **confiabilidade** (não perder nem duplicar mensagem com falha e reentrega) e **estado** (milhares de conversas abertas ao mesmo tempo, cada uma com dono, fila e histórico corretos).

**A solução em 4 frases.**
1. A IA é um atendente dentro de filas configuráveis, como um humano; o humano entra por escala, com resumo e histórico.
2. Toda mudança numa conversa passa por uma única função (`transicionar`), que trava a conversa, confere a transição, descarta resposta de dono antigo e grava estado, auditoria e eventos de saída na mesma transação.
3. Na integração com o agente, nada se perde e nada se repete: outbox na saída, inbox (deduplicação) nas pontas, broker que só confirma depois do Kafka e do núcleo.
4. Um experimento por ablação desliga cada proteção e mostra, contando nas pontas, que a falha que ela evita aparece só quando ela está desligada.

### O caminho de uma mensagem, em 10 passos

Decore este caminho: quase toda pergunta técnica cai em um destes passos.

| # | O que acontece | Onde no código |
|---|---|---|
| 1 | Cliente manda mensagem. A entrada deduplica pelo `id_externo` do canal (inbox) | `nucleo/api/mensagens.py`, `receber` e `chave_entrada` |
| 2 | Conversa nova: triagem por palavras-chave, roteador escolhe a fila, `transicionar` leva de `nova` para `na_fila` e grava a mensagem | `triagem.triar`, `acoes.rotear_conversa`, `roteador.rotear`, `mensagens._processar` |
| 3 | Distribuidor pega a conversa (`SKIP LOCKED`), escolhe o atendente e chama `transicionar` (`na_fila` para `com_ia`). Na mesma transação: atribuição nova e `conversa.atribuida` na outbox | `infra/distribuidor._ciclo`, `dominio/distribuicao.escolher` |
| 4 | Relay reserva o item da outbox e faz `POST /webhook` no broker, fora da transação | `infra/relay._processar_um`, `RESERVAR`, `_post` |
| 5 | Broker publica no tópico `helpdesk.para-agente` com chave `id_conversa`, espera o ack do Kafka e só então responde 200 | `broker/main.py`, `webhook` |
| 6 | Relay marca `enviado` e só agora cria o prazo do agente (`timeout_agente`, 30 s) | `relay.criar_timeout` |
| 7 | Agente mock consome, deduplica na inbox dele, decide e grava a resposta com id determinístico; um laço publica em `agente.para-helpdesk` | `agente_mock/main.py`, `_tratar`, `decidir`, `publicar` |
| 8 | Broker consome a volta, chama `POST /agente/eventos` e só confirma o offset depois do 2xx do núcleo | `broker/main.py`, `volta` |
| 9 | Núcleo: inbox, `transicionar` com o `id_atribuicao` do evento (fencing), grava a resposta, põe a entrega ao canal na outbox e cancela o prazo | `nucleo/api/agente.py`, `receber`, `_aplicar`, `_cancelar_prazos` |
| 10 | Relay entrega ao simulador de canais, que grava a entrega para o juiz do experimento | `relay._post` para `canais/main.py`, `entregar` |

---

## 2. Glossário com analogias

| Termo | O que é, com analogia | Onde aparece |
|---|---|---|
| **Webhook** | Uma chamada HTTP que um sistema faz para avisar outro que algo aconteceu. Como o porteiro que interfona quando chega uma encomenda, em vez de você descer toda hora para ver | Núcleo chama `POST /webhook` do broker: `relay._post`; recebido em `broker/main.py`, `webhook` |
| **Broker** | O componente que faz a ponte entre o webhook (HTTP) e o Kafka. É o despachante da transportadora: recebe o pacote no balcão e põe no caminhão certo | `broker/main.py` (sem banco, único que fala com o Kafka) |
| **Kafka** | Um log de mensagens durável e ordenado, que vários leitores consomem no próprio ritmo. Como um livro-caixa onde só se acrescenta linha, e cada leitor marca até onde já leu | Redpanda (API Kafka) no `docker-compose.yml`; cliente `aiokafka` no broker e no mock |
| **Tópico** | Um "livro" separado do Kafka para um assunto | `helpdesk.para-agente`, `agente.para-helpdesk`, `helpdesk.erros` (`broker/main.py`, `IDA`, `VOLTA`, `ERROS`) |
| **Partição** | Um tópico dividido em pedaços paralelos; a ordem só é garantida dentro de cada pedaço. Como os caixas de um banco: cada fila anda na ordem, mas filas diferentes andam em paralelo | 12 partições por tópico de ida e volta (impl 3) |
| **Chave** | O valor que decide em qual partição a mensagem cai. Mesma chave, mesma partição, mesma ordem | `id_conversa`: `broker.webhook` (`key=`) e `agente_mock.publicar` |
| **Offset** | A posição de uma mensagem dentro da partição: o número da linha no livro-caixa | `consumidor.commit({tp: msg.offset + 1})` em `broker.volta` |
| **Grupo de consumidores** | Leitores que dividem as partições entre si; cada partição tem um leitor no grupo. Não há mais leitores ativos que partições (doc do Kafka, `[doc]`, secundária) | `group_id="broker-volta"` e `group_id="agente-mock"` |
| **Commit (do offset)** | Avisar o Kafka "li até aqui". Se o leitor cair antes do commit, relê de onde parou. Por isso o commit vem **depois** do efeito | `enable_auto_commit=False` no broker e no mock |
| **Outbox** | Tabela onde o evento de saída é gravado na mesma transação do estado; outro processo (o relay) envia depois. Como deixar a carta na caixa de saída do escritório junto com o registro do protocolo: se o carteiro faltar hoje, a carta continua lá | `transicionar` (INSERT em `outbox`), `infra/relay.py` |
| **Relay** | O "carteiro" da outbox: reserva um item, envia, grava o resultado, tenta de novo com espera crescente | `relay._processar_um`, `atraso`, `trabalhador` |
| **Inbox** | Tabela de "já processei este id". Repetido é ignorado. Como o carimbo de "pago" no boleto: se o boleto chegar de novo, você vê o carimbo e não paga duas vezes | `eventos_processados` (consumidores `entrada` e `nucleo`), tabela `inbox` do mock |
| **Idempotência** | Fazer a mesma operação duas vezes tem o mesmo efeito que uma vez. Apertar o botão do elevador duas vezes não chama dois elevadores | Inbox mais `UNIQUE (id_evento)` em `mensagens` e `outbox` (migration 0002) |
| **Id determinístico** | Id calculado a partir da causa, não sorteado: reprocessar a mesma entrada gera o mesmo id, e a inbox do outro lado pega a repetição | `contrato/ids.py`, `id_derivado` (uuid5); `mensagens.chave_entrada`; `agente_mock._evento` |
| **Atribuição** | O "contrato de posse" da conversa por um atendente, com um id próprio. Muda de dono, muda o id | Tabela `atribuicoes`; coluna `conversas.id_atribuicao_atual`; criada em `transicionar` |
| **Fencing** | Descartar o pedido que traz uma atribuição vencida. Como trocar a fechadura quando o inquilino sai: a chave antiga não abre mais | `transicionar`, bloco `if config.FENCING_ATIVO and id_atribuicao ... != c["id_atribuicao_atual"]`; auditado como `evento_descartado` |
| **Máquina de estados** | A conversa só pode estar em seis estados e só pode ir de um para outro por caminhos permitidos, cada um com o ator que pode disparar. Como um semáforo que não pula do verde para o vermelho sem passar pelo amarelo | Tabela `transicoes_permitidas` (impl 6); `CHECK` dos seis estados (migration 0002); `transicionar._permitida` |
| **`transicionar`** | A única porta de escrita na conversa: trava, confere, grava tudo junto ou nada | `nucleo/dominio/transicionar.py`, `transicionar` |
| **`SKIP LOCKED`** | Na consulta, pula linhas que outro processo já travou, em vez de esperar. Como caixas de supermercado: se um caixa está ocupado, o cliente vai para o próximo livre | `relay.RESERVAR`, `distribuidor.PEGAR`, `agendador._agir` |
| **Roteador como função pura** | Recebe os dados do atendimento e as regras, devolve a fila; não lê banco nem relógio. Mesma entrada, mesma saída, sempre. Por isso dá para reproduzir decisão antiga e simular regra nova | `nucleo/dominio/roteador.py`, `rotear`; usado em `acoes.rotear_conversa` e `api/filas.simular` |
| **Distribuidor** | Laço que, a cada 1 s, tira conversas das filas e entrega a um atendente com vaga, uma conversa por transação | `nucleo/infra/distribuidor.py`, `_ciclo`; escolha em `dominio/distribuicao.escolher` |
| **Handoff** | Passar a conversa da IA para o humano com motivo, resumo e histórico | `acoes.escalar`; painel em `nucleo/api/painel.py` |
| **Human-in-the-loop** | O humano participa do fluxo da IA: recebe escalas, assume e pode devolver para a IA com uma nota | `painel.assumir`, `painel.devolver` (`conversa.devolvida`) |
| **Ablação** | Desligar uma peça por vez para ver o que ela evita. Como tirar o airbag do carro de teste para medir o que ele faz | Chaves `OUTBOX_ATIVA`, `INBOX_ATIVA`, `FENCING_ATIVO`, `TIMEOUT_ATIVO` em `nucleo/config.py`; `carga/rodar.py`, `CHAVES` |
| **Juiz nas pontas** | Contar o que o cliente mandou e o que o cliente recebeu, não o que o sistema diz de si mesmo. Como conferir a entrega pelo recibo do destinatário, não pelo relatório da transportadora | `carga/juiz.py`, `julgar`; entregas gravadas no database `canais` (`canais/main.py`) |
| **Reconciliador** | Consulta que confere regras que nunca deveriam ser violadas (invariantes), como "nenhuma resposta duplicada". O juiz diz se houve falha; o reconciliador ajuda a explicar onde | `nucleo/reconciliacao.py` (I1 a I6), `GET /supervisor/reconciliacao` |
| **Lei de Little** | L = λ × W: itens no sistema = taxa de chegada × tempo que cada um fica. Se chegam 2 clientes por minuto e cada um fica 10 minutos, há 20 na loja | arq 3 (conversas abertas); impl 11 (tarefas do relay: ~108 itens/s × ~15 ms ≈ 1,6, daí `RELAY_WORKERS = 8`) |
| **Contrapressão** | Quando o destino não aguenta, a origem para de empurrar e espera, em vez de jogar fora. A torneira fecha quando a pia enche | Broker pausa a partição em 503 ou falha de rede (`consumidor.pause`/`resume` em `broker.volta`); núcleo devolve 503 com banco fora (`nucleo/main.py`, `banco_fora`) |
| **Pelo menos uma vez** | Garantia de que a mensagem chega, talvez repetida. É o que a rede consegue dar | Retentativa do relay e do broker |
| **Exatamente uma vez** | Cada mensagem tem efeito uma vez só. Na rede não existe sozinho; obtém-se com "pelo menos uma vez" mais deduplicação no destino. É o mesmo princípio do exactly-once do Kafka: escrita idempotente e transacional (Wang et al., 2021, `[revisado]`) | Retentativa + inbox + id determinístico (arq 11) |

---

## 3. Decisão por decisão

Para cada uma: problema do case, decisão, falha que evita, evidência (só de `referencias.md`, com o tipo), onde no código, como mostrar na demo. Os números entre parênteses são as decisões da tabela da arq 20.

### D1. Monólito modular; broker e agente mock fora do núcleo (8)

- **Problema.** Um help desk com vários módulos (entrada, filas, painel, integração), feito por uma pessoa em prazo curto.
- **Decisão.** Um núcleo só (`nucleo/`) com módulos separados (`api`, `dominio`, `infra`). Saem do núcleo só o broker e o mock, porque espelham a fronteira real com a CloudWalk e o experimento os derruba (arq 9).
- **Falha que evita.** Custo de rede, de deploy e de consistência entre serviços sem ganho; anti-padrões de microsserviço.
- **Evidência.** Auer et al. (2021), `[revisado]`: migrar para microsserviços é caro, começar com monólito modular. Taibi et al. (2019), `[revisado]`: anti-padrões a evitar se algum serviço for extraído.
- **Onde.** `nucleo/` (API em `nucleo/main.py`, laços em `nucleo/trabalhador.py`); `broker/main.py`; `agente_mock/main.py`; serviços no `docker-compose.yml`.
- **Demo.** Slide com o diagrama da arq 9 (0:00 a 0:20).

### D2. Conversa como máquina de estados, com um único caminho de escrita (4, 15)

- **Problema.** Milhares de conversas abertas, com eventos chegando ao mesmo tempo do cliente, do agente, do analista e do agendador.
- **Decisão.** Seis estados (`nova`, `na_fila`, `com_ia`, `escalada`, `com_humano`, `resolvida`), transições permitidas numa tabela, e toda mudança por `transicionar`, numa transação: trava a conversa (`FOR UPDATE`), fencing, confere a transição, confere a capacidade do novo dono **antes** de soltar o antigo, grava estado, mensagem, auditoria e outbox juntos. Rejeição volta como resultado, não como exceção.
- **Falha que evita.** Transições simultâneas, capacidade estourada, duas conversas abertas para o mesmo cliente, conversa sem dono depois de `SEM_CAPACIDADE`.
- **Evidência.** Bailis et al. (2015), `[revisado]` (resumo): em 67 aplicações Rails, unicidade validada só na aplicação gerou duplicata; por isso trava e índice único no banco. Warszawski e Bailis (2017), `[revisado]` (resumo): 22 ataques por concorrência em 12 aplicações.
- **Onde.** `nucleo/dominio/transicionar.py`, `transicionar`, `_permitida`, `_atendente_com_capacidade`, `encerrar_atribuicao`. Índice único parcial `conversa_aberta_unica` em `migrations/versions/0002_nucleo_confiavel.py`; repetição em `mensagens.receber` (laço de 2 tentativas com `IntegrityError`).
- **Demo.** `GET /conversas/{id}`: a auditoria mostra `triagem`, `decisao_roteamento`, `decisao_distribuicao`, `transicao` na ordem `nova → na_fila → com_ia`.

### D3. Fencing por `id_atribuicao` (13, 15)

- **Problema.** O agente pode responder depois que a conversa já foi para um humano.
- **Decisão.** Todo evento do agente carrega o `id_atribuicao` que recebeu. Se for diferente da atribuição vigente, `transicionar` descarta e audita.
- **Falha que evita.** Resposta atrasada da IA caindo no atendimento humano.
- **Evidência.** Kleppmann (2016), `[mercado]`: fencing token, que aqui é o `id_atribuicao`. Gray e Cheriton (1989), `[revisado]` (resumo): lease, direito com prazo.
- **Onde.** `transicionar.py`, primeiro bloco depois da trava; o envelope exige `id_atribuicao` e `causado_por` nos eventos do agente (`contrato/envelope.py`, `regras_do_contrato`); invariante I4 em `nucleo/reconciliacao.py`.
- **Demo.** Mock em `lento`: a conversa escala por timeout e, ~5 s depois, a resposta atrasada aparece na auditoria como `evento_descartado` com `atribuicao_vencida`; `GET /supervisor/metricas` conta `descartes_fencing_ultima_hora`. É o cenário 6 da fumaça.

### D4. Outbox transacional com relay (9, 16)

- **Problema.** O núcleo precisa salvar o estado e avisar o agente. São duas operações; se cair entre elas, perde ou inventa.
- **Decisão.** O evento vai para a tabela `outbox` na mesma transação do estado. O relay envia depois, um item por vez: reserva curta, envio fora da transação, resultado em transação nova. Ordem por conversa **e destino**. Retentativa com backoff exponencial, teto e jitter; esgotou (8 tentativas), vira `erro`, e se o destino era o broker a conversa escala por `falha_integracao`. Itens em `erro` voltam por `POST /outbox/{id}/reprocessar`.
- **Falha que evita.** Perda entre commit e envio; evento que sempre falha travando o relay inteiro; falha no canal segurando a mensagem seguinte para o agente.
- **Evidência.** Richardson, transactional outbox, `[doc]`: a mensagem sai se e só se a transação confirmar. Helland (2007), `[revisado]`: sem transação distribuída, outbox mais idempotência. Yuan et al. (2014), `[revisado]` (resumo): 92% das falhas catastróficas estudadas vieram de tratamento errado de erro não fatal. AWS Builders' Library, `[mercado]`: backoff com teto e jitter.
- **Onde.** INSERT na outbox em `transicionar`; `nucleo/infra/relay.py`, `RESERVAR` (o `NOT EXISTS` garante a ordem), `_processar_um`, `atraso`, `reprocessar`. Ablação em `relay.enviar_direto` e `infra/banco.unidade`.
- **Demo.** `docker compose stop broker`; mandar mensagem; `GET /supervisor/metricas` mostra `outbox` com `pendente`; `docker compose start broker`; a fila drena.

### D5. Inbox nas pontas e id determinístico (14)

- **Problema.** Canais reenviam (o WhatsApp reenvia webhook), o relay e o broker retentam, o Kafka reentrega.
- **Decisão.** Inbox `eventos_processados(consumidor, id_evento)` na mesma transação do efeito, na entrada dos canais (chave `uuid5(canal, id_externo)`), na API do agente e no mock. Eventos derivados com id `uuid5(causado_por, tipo, sequencia)`. O broker não tem inbox: a deduplicação fica nas pontas.
- **Falha que evita.** Cliente recebendo a resposta em dobro; uma mensagem virando duas.
- **Evidência.** Saltzer, Reed e Clark (1984), `[revisado]`: deduplicação e entrega garantida só ficam completas nas pontas. Helland (2012), `[revisado]`: a operação precisa ter o mesmo efeito se repetida.
- **Onde.** `nucleo/api/mensagens.py`, `receber`; `nucleo/api/agente.py`, `receber`; `agente_mock/main.py`, `_tratar`; `contrato/ids.py`, `id_derivado`.
- **Demo.** Reenviar `POST /mensagens` com o mesmo `id_externo`: a resposta vem com `"duplicada": true`. Mock em `duplicar`: cada resposta é publicada duas vezes e o cliente recebe uma.

### D6. Broker: 200 só depois do Kafka; offset só depois do núcleo; contrapressão (17, 17b)

- **Problema.** O broker é o ponto onde a mensagem troca de meio (HTTP para Kafka e de volta). Pode perder em qualquer um dos lados.
- **Decisão.** Ida: responde 200 ao webhook só depois do ack do Kafka (`acks=all`, produtor idempotente); falha do Kafka = 503, e o relay tenta de novo. Volta: confirma o offset só depois do 2xx do núcleo. 503 ou rede: pausa a partição, espera e retoma, sem limite e sem deixar de consultar o Kafka. 4xx ou JSON inválido: `helpdesk.erros`. 500 repetido: `helpdesk.erros` depois de `RETENTATIVAS_MAX`, e a conversa escala pelo `timeout_agente` pendente.
- **Falha que evita.** Perda entre webhook e Kafka, ou entre Kafka e núcleo; um evento ruim travando a partição.
- **Evidência.** Wang et al. (2021), `[revisado]`; Saltzer et al. (1984), `[revisado]`; documentação do aiokafka, `[doc]` (página): `pause`/`resume` sem rebalance; `max_poll_interval_ms` de 300 s.
- **Onde.** `broker/main.py`, `webhook` e `volta` (dentro, `particao`); 503 do núcleo em `nucleo/main.py`, `banco_fora` e `rede_fora`.
- **Demo.** O mesmo trecho do broker fora (D4).

### D7. Contrato JSON versionado; Kafka particionado por conversa (7, 13, 34)

- **Problema.** O formato da "estrutura atual" da CloudWalk não é público (arq 2), e eventos guardados convivem em versões diferentes.
- **Decisão.** Envelope com `versao` (`^1\.\d+$`), `id_evento`, `tipo`, `id_conversa` (chave de partição, ordem dentro da conversa), `id_atribuicao`, `causado_por`, `marca`, `timestamp` com fuso. Dentro da versão 1 só se acrescenta campo opcional; o leitor ignora campo desconhecido; tipo desconhecido é auditado e confirmado.
- **Falha que evita.** Campo novo quebrando consumidor antigo; mensagens da mesma conversa fora de ordem; "13:30" ambíguo entre Brasil e EUA.
- **Evidência.** Overeem et al. (2021), `[revisado]` (resumo; ordem das táticas por fonte secundária): cinco táticas de evolução de esquema em sistemas *event sourced*, por analogia. Chatwoot agent bot, `[doc]`, como base do formato.
- **Onde.** `contrato/envelope.py`, `Envelope`, `regras_do_contrato`; tipo desconhecido em `nucleo/api/agente.py`, `receber` (`so_tipo`).
- **Demo.** Na auditoria da conversa, mostrar `id_atribuicao` e `causado_por` ligando a resposta à mensagem.

### D8. Prazo do agente contado do ack do broker; agendador único (18)

- **Problema.** Saber quando o agente "sumiu" sem culpá-lo pelo atraso da própria plataforma.
- **Decisão.** O `timeout_agente` (30 s) só nasce quando o broker confirma o envio, na transação do relay que marca `enviado`. Evento parado na outbox não cobra o agente; quem escala nesse caso é o esgotamento do relay. Um agendador só, com tabela `agendamentos`, um item por transação com `SKIP LOCKED`. Na subida do núcleo, prazos vencidos ganham um prazo inteiro.
- **Falha que evita.** Prazos espalhados pelo código; escalar conversa porque a plataforma atrasou; escala em massa depois de reiniciar o núcleo.
- **Evidência.** Dai et al. (2018), `[revisado]` (slides): valor errado e checagem ausente dominam os bugs de timeout. Que um ponto único reduza esses erros é **inferência nossa** (está escrito assim em arq 11.5).
- **Onde.** `relay.criar_timeout`; `nucleo/infra/agendador.py`, `_agir`, `laco`, `reagendar_na_subida`; cancelamento em `agente._cancelar_prazos` (responder uma mensagem cobre as anteriores).
- **Demo.** Mock em `lento` ou parado: a conversa escala 30 s depois do envio, com motivo `timeout_agente`.

### D9. IA como atendente dentro de filas no modelo Zendesk; roteador como função pura (5, 6, 21, 33)

- **Problema.** A operação tem marcas, equipes e assuntos diferentes, e algumas filas devem ir direto para humanos.
- **Decisão.** Fila = condições + ordem + prioridade + lista ordenada de grupos de atendentes (IA ou equipe). A primeira fila que casa leva; sem casamento, fila padrão. A IA é um grupo como outro qualquer. O roteador é uma função pura.
- **Falha que evita.** IA como "etapa fixa" que não dá para tirar de uma fila; decisão de roteamento que não dá para reproduzir nem simular.
- **Evidência.** Zendesk, `[doc]`: fila = condições + ordem + prioridade, primeira que casa leva, grupo primário e secundário. Chatwoot agent bots, `[doc]`: bot como atendente, handoff por status. Gans, Koole e Mandelbaum (2003), `[revisado]`: base de filas e roteamento por habilidade.
- **Onde.** `nucleo/dominio/roteador.py`, `rotear`, `condicoes_que_casam`; filas iniciais em `nucleo/infra/seed.py`, `FILAS_V1` (por exemplo, `infinitepay-fraude` só com humanos).
- **Demo.** `POST /filas/simular` com um atendimento e a resposta mostrando fila, regra e versão.

### D10. Filas versionadas, com validação de valor, ativação atômica e rollback (20)

- **Problema.** "Filas configuráveis pela operação, sem deploy" (requisito 2), sem que um erro de digitação derrube o atendimento.
- **Decisão.** Cada edição gera uma versão imutável em `versoes_regras` (JSONB). Antes de criar e de ativar, valida campo, operador **e valor** (por exemplo, `"JIM"` maiúsculo é recusado), fila padrão, ids e ordens sem repetição, grupos existentes. Ativar é atômico (trava `pg_advisory_xact_lock(42)` e índice único `uma_versao_ativa`). Rollback = ativar a versão anterior. Cada roteamento lê a versão ativa no banco.
- **Falha que evita.** Configuração errada derrubando o sistema; instâncias com regras diferentes; não saber qual regra levou a conversa para a fila.
- **Evidência.** Tang et al. (2015), `[revisado]`: erro de configuração derruba sistemas; resposta com versão, validação e revisão.
- **Onde.** `nucleo/api/filas.py`, `criar`, `ativar`, `validar_regras`, `simular`; `roteador.validar`; a versão usada fica em `conversas.versao_regras` e no evento `decisao_roteamento`.
- **Demo.** Trecho 1:05 a 1:50 (seção 6).

### D11. Distribuidor em laço, AI first por grupo e ocupação; escala volta ao roteador (25, 37)

- **Problema.** Escolher entre IA e humanos sem inverter o AI first e sem duas instâncias pegarem a mesma conversa.
- **Decisão.** A cada 1 s, monta as filas que têm algum atendente livre e pega uma conversa por transação com `SKIP LOCKED`, na ordem: prioridade da fila, escaladas antes, prioridade da conversa, espera. A escolha é pura: primeiro o grupo preferido da fila, depois a menor ocupação dentro dele. `SEM_CAPACIDADE` tira a fila do ciclo, e fila lotada não segura as outras. Escalada volta ao roteador com `origem = escalado` e cai na fila de escalas da marca; o distribuidor não a devolve para a IA. Cada distribuição grava candidatos, carga, capacidade, escolhido e motivo.
- **Falha que evita.** Analista com 1 conversa passando na frente da IA (comparar só ocupação inverteria o AI first: comentário em `distribuicao.py`); travas cruzadas entre instâncias; decisão sem explicação.
- **Evidência.** Zendesk, `[doc]` (grupo primário e secundário). Não há artigo específico para o algoritmo de escolha em `referencias.md`; a justificativa é de desenho.
- **Onde.** `nucleo/infra/distribuidor.py`, `PEGAR`, `_candidatos`, `_ciclo`; `nucleo/dominio/distribuicao.py`, `escolher`.
- **Demo.** No detalhe da conversa, o evento `decisao_distribuicao` com a lista de candidatos e o motivo `preferencia_e_menor_ocupacao`.

### D12. Handoff com resumo, fontes e resumo de reserva (35)

- **Problema.** O analista precisa entender o caso sem ler tudo, e não pode confiar num resumo inventado.
- **Decisão.** `conversa.escalada` traz motivo, resumo, prioridade sugerida e `fontes` (ids das mensagens que sustentam o resumo). Escala por timeout ou falha usa resumo de reserva **extrativo** (triagem mais as últimas mensagens do cliente, sem texto novo), marcado `reserva = true`. O cliente recebe pelo canal uma mensagem de transferência. O analista assume, responde, devolve para a IA com nota ou encerra.
- **Falha que evita.** Analista agindo sobre resumo alucinado; cliente sem saber que mudou de atendente.
- **Evidência.** Maynez et al. (2020), `[revisado]` (resumo): conteúdo alucinado em quantidade substancial nos resumos de todos os modelos avaliados. Wang et al. (2026), `[preprint]` (resumo): intervenção humana preserva qualidade nas escalas técnicas, é menos eficaz nas emocionais disparadas por algoritmo; intervir cedo. Luo et al. (2019), `[revisado]`: cliente desconfia de bot revelado, então transparência e handoff fácil.
- **Onde.** `nucleo/dominio/acoes.py`, `escalar`, `resumo_de_reserva`, `MSG_TRANSFERENCIA`; `agente_mock/main.py`, `decidir` (escala com `fontes`); `nucleo/api/painel.py`.
- **Demo.** `GET /painel/fila` mostra `motivo`, `resumo`, `fontes` e `reserva`; o front destaca as mensagens das fontes.

### D13. Memória operacional: perfil de fatos e últimas N mensagens lidas sob a trava (27)

- **Problema.** Requisito 8 (memória entre interações) sem custo e risco de mandar tudo ao agente.
- **Decisão.** `conversa.atribuida` e `conversa.devolvida` levam as últimas 20 mensagens (`HISTORICO_N`), lidas dentro de `transicionar` com a conversa travada, e um perfil só com fatos contáveis (contatos e escalas em 30 dias, canal preferido, último assunto). Nunca traço de personalidade.
- **Falha que evita.** Histórico inteiro (caro, expõe dado pessoal, mal usado pelo modelo); agente perguntando de novo o que o cliente já disse; mensagem que chegou no meio ficando fora do contexto.
- **Evidência.** Liu et al. (2024), `[revisado]` (resumo): informação no meio de contexto longo é mal usada. LGPD, `[doc]`: art. 6º, III (mínimo necessário) e art. 20 (revisão de decisão automatizada que defina perfil).
- **Onde.** `acoes.contexto_para_ia`, `ultimas_mensagens`, `perfil_operacional`; chamado nas saídas do distribuidor e do `painel.devolver`.
- **Demo.** `GET /conversas/{id}` devolve `perfil`.

### D14. Auditoria só de inserção e registro de decisão (requisito 7; 25)

- **Problema.** Requisito 7: auditar cada decisão de atendimento e de escala.
- **Decisão.** Tabela `eventos` que recusa `UPDATE` e `DELETE` por trigger. Cada roteamento grava os oito campos, a versão, a fila e a regra; cada distribuição grava os candidatos. Com roteador puro e versão imutável, a decisão é reproduzível.
- **Falha que evita.** Saber para onde a conversa foi, mas não por quê; histórico alterado depois.
- **Evidência.** Não há artigo próprio em `referencias.md`; a base é o requisito do enunciado e o princípio 5 da arq ("tudo vira evento registrado").
- **Onde.** `transicionar.auditar`; trigger `tg_eventos_imutaveis` em `migrations/versions/0002_nucleo_confiavel.py`; `acoes.rotear_conversa`; `distribuidor._ciclo`.
- **Demo.** A lista `auditoria` em `GET /conversas/{id}`.

### D15. Experimento por ablação, juiz nas pontas e reconciliador (12, 19, 38)

- **Problema.** Provar robustez "diante de falhas, reentregas e picos" sem duas versões do sistema.
- **Decisão.** Uma versão só, a robusta, com chaves que desligam cada proteção. Cada cenário roda com a chave ligada e desligada: E1 base, E3b reenvio de 10% das mensagens 2 s depois (inbox), E6 broker fora por 60 s no minuto 8 (outbox). O juiz conta pelo que o gerador enviou e pelo que o simulador de canal entregou; a escala só conta pela mensagem de transferência vista na ponta. O reconciliador explica a causa.
- **Falha que evita.** Comparar versões diferentes (diferença de código, não de proteção); o sistema "dar nota para si mesmo".
- **Evidência.** Basiri et al. (2016), `[revisado]`: falhas injetadas com medida de estado estável. Saltzer et al. (1984), `[revisado]`: base do juiz nas pontas. Yuan et al. (2014), `[revisado]`: testar o caminho de erro.
- **Onde.** `nucleo/config.py` (chaves); `carga/agenda.py` (agenda com semente 42), `carga/gerador.py`, `carga/falhas.py`, `carga/rodar.py`, `carga/lote.py`, `carga/juiz.py`, `carga/tabelas.py`; `nucleo/reconciliacao.py`.
- **Demo.** Trecho 3:50 a 4:40: tabelas do E3b, do E6 e o p95 do E1 **[preencher com o resultado]**.

---

## 4. As 25 perguntas mais prováveis

**1. Por que não microsserviços?**
O volume é baixo (arq 3) e a dificuldade é consistência de estado, que fica mais fácil numa transação do mesmo banco. Monólito modular, e só sai do núcleo o que precisa falhar de forma independente: broker e mock, porque o experimento os derruba e eles espelham a fronteira real. Auer et al. (2021) e Taibi et al. (2019), ambos `[revisado]`.

**2. Por que Python e não Ruby, se a CloudWalk usa Ruby?**
Velocidade de entrega no prazo e domínio do desenvolvedor (arq 15). Os componentes só conversam por HTTP, Kafka e JSON Schema, então dá para migrar um por vez para Ruby. A migração está em Evolução (README).

**3. Por que Kafka e não uma fila simples?**
Primeiro, porque o enunciado pede integração por webhook, broker e Kafka "no formato da estrutura atual" (requisito 4). Segundo, a chave `id_conversa` dá ordem por conversa com paralelismo entre conversas (12 partições). Dentro do núcleo não usamos Kafka: a fila é o Postgres (outbox, agendamentos, `SKIP LOCKED`), porque precisamos da transação junto com o estado. Comparação de brokers em Dobbelaere e Esmaili (2017), `[revisado]`.

**4. Como vocês provam que não perdem mensagem?**
Três camadas. Por desenho: outbox, offset depois do efeito, inbox. Por teste: a fumaça de ponta a ponta (19 cenários, README). Por experimento: no E6, com a outbox desligada a perda deve aparecer e com ela ligada deve ser zero, contada nas pontas pelo juiz, não pelo banco **[preencher com o resultado]**. O reconciliador (I1, I2) aponta onde.

**5. E se o agente cair?**
O prazo de 30 s vence, a conversa escala com resumo de reserva e o cliente recebe a transferência. As mensagens ficam no Kafka; quando o agente volta, responde, e o que for de atribuição vencida o fencing descarta. Ponto fraco: sem disjuntor (Evolução), as conversas novas continuam indo para a IA e escalam 30 s depois; é a falha metaestável da arq 11.9.

**6. E se o broker cair?**
A outbox acumula e o relay tenta de novo com backoff. Como o prazo do agente só nasce no ack, ninguém escala por timeout por causa disso. Se a queda passar das 8 tentativas (de 61,5 s a 123 s com os valores iniciais, impl 7.3), o item vai para `erro` e a conversa escala por `falha_integracao`. Respostas que estavam no Kafka quando o broker caiu podem escalar por timeout: aparecem como escala, não como perda.

**7. E se o núcleo ou o banco cair?**
O broker recebe 503 ou conexão recusada, pausa a partição e não confirma o offset: nada se perde, só atrasa (contrapressão). Na volta, `reagendar_na_subida` dá um prazo inteiro aos timeouts vencidos, para não escalar em massa. Limitações: o E7 (núcleo morto) não foi medido, e o Postgres não tem réplica.

**8. Por que 50 msg/s e não 100?**
Nesta máquina o sistema sustentou cerca de 35 msg/s de cliente (70 no total) antes de começar a recusar, com gerador, broker, Kafka, Postgres e mock juntos (README). A arq 19.2 já previa cair para 50 se a máquina não aguentasse, declarado. Pela conta da arq 3, 50 msg/s fica acima do pico de estresse com 5x (~35) e abaixo do pico concentrado (~70). A meta de 100 fica sem evidência.

**9. O que acontece com uma resposta atrasada do agente?**
Ela traz o `id_atribuicao` antigo. Se a conversa já escalou ou mudou de dono, `transicionar` descarta e grava `evento_descartado` com `atribuicao_vencida`. O cliente não recebe e o humano não é atropelado. A invariante I4 confere que nenhuma resposta foi gravada fora do dono.

**10. "Exatamente uma vez" existe?**
Não na rede. O que existe é entrega pelo menos uma vez com deduplicação nas pontas que controlamos (entrada, núcleo, mock, saída). Onde não controlamos o receptor (canal real, agente real), é pelo menos uma vez. O mesmo princípio está no exactly-once do Kafka (Wang et al., 2021).

**11. Como evitam resposta duplicada?**
O mock gera id determinístico (`id_derivado`); a inbox do núcleo descarta o repetido; `mensagens.id_evento` é único; a invariante I3 confere. Requisito do contrato: o agente real também precisa gerar id determinístico, senão a deduplicação no núcleo não pega a reentrega.

**12. O que é limitação e o que é defeito?**
Limitação é escolha consciente, escrita, com o efeito declarado (por exemplo, Redpanda sem fsync). Defeito é o sistema fazer diferente do que promete, ou uma limitação escondida. A régua da revisão: "limitação declarada com o efeito não tira ponto; corrigível não feito, ou limitação escondida, tira" (rodada 4). Por isso a lista de limitações do README é longa.

**13. Por que o resumo tem fontes?**
Porque resumo abstrativo alucina: Maynez et al. (2020), `[revisado]`, acharam conteúdo alucinado em todos os modelos avaliados. Com `fontes`, o analista clica e confere na mensagem original. Sem fontes, aparece marcado. Na escala por timeout, o resumo é extrativo: só copia triagem e mensagens. A qualidade do resumo não foi medida (limitação).

**14. Por que não usaram embeddings ou rede neural?**
O requisito de memória é atendido pela memória operacional (fatos por SQL). Embeddings e casos parecidos (D6) foram para Evolução pela decisão D-2: custo de serviço, pgvector e conjunto rotulado. A triagem é por regras; um classificador está em discussão (Mozannar e Sontag, 2020, `[revisado]`). E o foco avaliado é a robustez da plataforma, não a inteligência do agente, que está fora do escopo.

**15. Como a operação muda as filas sem deploy?**
Editando o JSON pela API: `POST /filas/validar`, `POST /filas/versoes` (versão nova, inativa) e `POST /filas/versoes/{n}/ativar`. Cada roteamento lê a versão ativa no banco, então a próxima conversa já usa a regra nova. Rollback é ativar a versão anterior. Base: Tang et al. (2015), `[revisado]`.

**16. O que o experimento prova e o que não prova?**
Prova (se os resultados confirmarem a previsão): numa máquina, a 50 msg/s, cada proteção (inbox, outbox) remove a falha que ela evita, contada nas pontas. Não prova: 100 msg/s, escala horizontal (H3), disjuntor (H2), interação entre proteções (uma chave por vez), variância (uma repetição), durabilidade de disco (Redpanda sem fsync), qualidade das respostas (mock com texto fixo), nem que o agente real cumpra o id determinístico.

**17. Por que o prazo do agente conta do ack do broker e não da hora em que a mensagem chegou?**
Para não culpar o agente pelo atraso da plataforma. Se o evento está parado na outbox, o agente nem recebeu. Nesse caso, quem escala é o esgotamento do relay. Limitação declarada: a fila no caminho de volta ainda conta contra o agente.

**18. Por que tudo passa por uma função só (`transicionar`)?**
Porque é o único lugar onde se garante, numa transação com trava, que estado, mensagem, auditoria e saída ficam coerentes. Validação só na aplicação, espalhada, gera duplicata sob concorrência (Bailis et al., 2015, resumo). Ordem de travas fixa evita deadlock.

**19. Por que o roteador é "função pura"?**
Porque não lê banco nem relógio: mesma entrada, mesma fila. Isso permite reproduzir qualquer decisão gravada (a auditoria guarda a entrada e a versão), testar em tabela e oferecer o simulador `POST /filas/simular` sem custo extra.

**20. Como o distribuidor escolhe entre IA e humano?**
Pela ordem dos grupos na fila: nas filas AI first a IA vem primeiro, e a equipe recebe quando a IA está sem vaga. Dentro do grupo, o de menor ocupação. Só depois a ocupação, porque comparar só ocupação poria um analista com 1 conversa na frente da IA com 800 e inverteria o AI first.

**21. Por que não mandar o histórico inteiro ao agente?**
Custa tokens, expõe mais dado pessoal (LGPD, mínimo necessário) e é mal usado pelo modelo: Liu et al. (2024), `[revisado]`, mostram queda quando a informação relevante está no meio de contexto longo. Vão as últimas 20 mensagens e o perfil de fatos, lidos sob a trava.

**22. E o painel, por que relê a cada 2 s em vez de WebSocket?**
2 s bastam para o painel e a demo, e evitam a conexão de `LISTEN`, a fila por navegador e a trava global do NOTIFY no commit (Levin, Recall.ai, 2025, `[mercado]`; doc do PostgreSQL, `[doc]`). SSE fica em Evolução (decisão D-2).

**23. Por que sentimento negativo não escala sozinho?**
Porque a evidência não sustenta um limiar de sentimento como gatilho: no experimento de campo do Alibaba (Wang et al., 2026, `[preprint]`, pelo resumo), a intervenção humana foi menos eficaz nas escalas emocionais disparadas por algoritmo. A triagem calcula o sentimento e a fila pode usá-lo como condição; escala-se por pedido do cliente ou do agente.

**24. Como é o multi-marca?**
`marca` está no contrato (`infinitepay` ou `jim`), na conversa, no cliente, nos atendentes e nas filas; o idioma segue a marca (pt ou en), e o mock responde como Claudio ou JIM. Limitações: marca é valor fixo (terceira marca exige deploy) e o isolamento é por filtro, sem Row-Level Security e sem autenticação.

**25. Você escreveu esse código? Como garante que entende?**
O backend foi escrito por um agente de código, e isso está declarado na arq 19. As decisões são minhas, discutidas e revisadas em quatro rodadas (`docs/revisoes/`), e o plano previa pontos de controle com uma página por componente no diário para eu defender o que não digitei. Consigo apontar cada decisão no código: [escolha uma de D2 a D12 e mostre a função].

---

## 5. Pontos fracos para admitir

Enquadramento geral: "isto foi escolha com efeito declarado, ou é algo que eu corrigiria assim". Não esconda; a régua da revisão pune limitação escondida, não declarada.

### Declarados no README (diga e mostre o efeito)

| Ponto fraco | Como enquadrar |
|---|---|
| A meta de 100 msg/s não foi medida; o experimento roda a 50 | Plano B escrito antes (arq 19.2); 50 cobre o pico de estresse com 5x (~35, arq 3). Uma máquina com tudo junto, e o gerador disputa CPU |
| Uma repetição por cenário, sem variância | Vale zero contra não zero e ordem de grandeza, não diferenças pequenas (arq 17) |
| Agente mock com texto fixo; qualidade do resumo não medida | O experimento mede a plataforma, não o agente, que está fora do escopo (TAPI) |
| Sem disjuntor: com o agente fora, todas as conversas com a IA escalam e as novas continuam indo à IA | Desenho pronto (arq 11.9, com as correções da rodada 3); cortado no plano de 2 dias. É falha metaestável conhecida (Huang et al., 2022, `[revisado]`, resumo) |
| Redpanda de um nó em modo de desenvolvimento, que confirma sem fsync | `acks=all` não garante durabilidade aqui; em produção, cluster com fsync (doc do Redpanda, `[doc]`) |
| Postgres sem réplica | Falha de disco ou de banco não é testada |
| Juiz depende do banco do núcleo para ligar resposta a mensagem | A contagem é das pontas; só a correspondência vem do banco; supõe uma resposta antes da mensagem seguinte (vale com 84 s entre mensagens) |
| Fila no caminho de volta conta contra o agente | Resposta presa no broker escala por timeout; aparece como escala, não como perda |
| Sem inatividade: conversa com humano esperando o cliente ocupa vaga até o analista encerrar | Poucas conversas esquecidas lotam um analista de 3 vagas; inatividade desenhada em arq 11.8 |
| Sem autenticação; isolamento por marca só por filtro | Perfil escolhido na tela; RLS em Evolução |
| Uma instância de cada serviço | Os laços usam `SKIP LOCKED` e o código diz que mais de uma instância é segura (`nucleo/trabalhador.py`), mas isso não foi medido (H3, E9) |
| Contrato é proposta nossa | O formato da CloudWalk não é público; o tradutor ficaria no broker, único que fala com o agente |
| Ablação desliga uma chave por vez | Não mede interação entre proteções |
| Canais simulados | Janela de 24 h do WhatsApp e encadeamento de e-mail ficam de fora |
| Backend escrito por agente de código | Declarado (arq 19); decisões revisadas em 4 rodadas; você aponta cada uma no código |

### Divergências entre documento e código que encontrei (corrija o doc ou declare antes da banca)

Nenhuma delas perde mensagem; são pontos em que o documento diz uma coisa e o código faz outra. Se a banca achar, é "defeito" pela régua; se você declarar antes, é transparência.

1. **Capacidade da IA.** A arq 19.1 e o README dizem "IA sem limite". No código, o seed dá à IA `CAPACIDADE_IA = 2000` (`nucleo/infra/seed.py`) e `transicionar` conta e trava a IA como um humano, por conversas abertas (`_atendente_com_capacidade` e `ativas + 1`), não por trabalho em voo como o desenho pede (arq 3). No experimento, `carga/rodar.py`, `preparar`, sobe a capacidade para 1.000.000, então o experimento está coerente com o README. Fora dele (demo), há teto de 2000 conversas abertas por IA. Enquadre: "no experimento, sem limite; no uso normal, um teto provisório por conversa aberta; a capacidade por trabalho em voo é Evolução".
2. **Envelhecimento de prioridade.** A arq (12, 19.1, decisão 10) diz que é Evolução. O código já soma `floor(espera / ENVELHECIMENTO_S)` (600 s) à prioridade da conversa em `distribuidor.PEGAR`, contando de `na_fila_desde`. Como a prioridade da fila vem antes na ordenação, a espera sem limite de uma fila de prioridade menor que divide equipe com outra continua possível (leitura do código; confira).
3. **Re-roteamento de fila removida.** A arq 19.1 diz que não entra. O código faz: `nucleo/api/filas.py`, `ativar`, re-roteia conversas em `na_fila` e `escalada` de fila que sumiu (o diário também diz que entrou). Aqui o código está à frente do documento.
4. **Comentário de `transicionar`.** A docstring diz "Ordem de travas: conversa -> agendamento -> atendente". O código trava o atendente novo antes de cancelar agendamentos, que é a ordem da arq 11.2 e da impl 7.1 (conversa, atendente novo, agendamentos, atendente antigo). O comentário está desatualizado.
5. **Jitter do relay sem semente.** `relay.atraso` usa `random.uniform` global; `RELAY_SEMENTE` não é lido. Já declarado em impl 7.3; o resultado do E6 não depende dele.
6. **Diário sem a entrada do dia 2.** A docstring de `carga/lote.py` e a impl 2 citam "diário, dia 2" para os ~35 msg/s e a separação do `trabalhador`, mas o `diario.md` só tem o ponto de controle do dia 1 e a fatia 1. A observação dos 35 msg/s está só no README e na docstring.
7. **Nome do bloco 5 da fumaça.** O bloco 5 de `testes/fumaca.py` se chama "Fencing", mas testa a checagem de dono do painel (`painel._dono`, 409). O fencing por `id_atribuicao` é o bloco 6 (agente lento). Se perguntarem, explique a diferença.

Itens da rodada 4 que o código já corrigiu, para você saber: a transferência sai com `causado_por` em todos os caminhos de escala (N13: `acoes.escalar` recebe `causado_por` do agendador, do relay, da API do agente e da entrada), e o juiz liga resposta a mensagem pela tabela `mensagens` nas duas posições da chave (N14, alternativa mais barata da revisão; `carga/juiz.py`).

---

## 6. Roteiro da demonstração de 5 minutos

Resumo da arq 19.4, ajustado ao que existe no código. Antes: `docker compose up -d --build` já feito e `.venv\Scripts\python testes\fumaca.py` passando. Tenha a gravação de reserva de cada falha.

**Dois ajustes ao roteiro da arq 19.4 (diga se perguntarem):**
- A arq fala em "k6 leve (2 conversas/s)" e em "contador do juiz" na tela. O k6 foi trocado pelo `carga/gerador.py`, e não há comando pronto para carga leve de fundo: `carga.rodar` não aceita taxa e `carga.lote` roda o experimento inteiro, reiniciando serviços. O juiz só roda no fim de uma execução. Recomendo a demo **sem carga de fundo**, usando `GET /supervisor/metricas` e `GET /supervisor/reconciliacao` no lugar do contador. Com 2 conversas/s e o agente fora, seriam ~840 conversas com a IA escalando (rodada 4, N15), o que afoga o painel.
- No trecho do handoff, use o modo `lento` do mock (está em `docs/api-front.md`): além da escala por timeout, a resposta atrasada chega ~5 s depois e aparece como `evento_descartado`. Isso mostra o fencing ao vivo.

Comandos no formato de `docs/api-front.md`. Em PowerShell, o equivalente é `Invoke-RestMethod -Method Post -Uri <url> -ContentType 'application/json; charset=utf-8' -Body '<json>'` (não testado neste guia; ensaie antes).

| Tempo | Na tela | Comandos | O que falar |
|---|---|---|---|
| 0:00 a 0:20 | Slide com o diagrama da arq 9 | — | "Canal, núcleo, broker, Kafka, agente. O agente fica fora do núcleo, como na CloudWalk. O volume é baixo; o desafio é não perder, não duplicar e manter o estado certo." |
| 0:20 a 1:05 | Chat simulado e acompanhamento | `POST /mensagens {"canal": "chat", "marca": "infinitepay", "identificador": "app-1001", "nome": "Loja da Ana", "conteudo": "meu repasse não caiu", "id_externo": "demo-1"}`; depois `GET /conversas/{id_conversa}` | "A mensagem passou pela triagem, pelo roteador e pelo distribuidor e foi para a IA pelo broker e pelo Kafka. Na auditoria: `nova → na_fila → com_ia`, a regra que casou, os candidatos, e a resposta com o `id_atribuicao` e o `causado_por`." |
| 1:05 a 1:50 | Editor de filas | `GET /filas/ativa`; editar (sugestão: fila `jim-repasse` só com a equipe `support-us`, condição `marca = jim` e `categoria = repasse`, ordem 6, e `jim-geral` para ordem 7); `POST /filas/validar`; `POST /filas/versoes {"regras": {...}, "criada_por": "supervisor"}`; `POST /filas/versoes/{n}/ativar`; `POST /filas/simular {"atendimento": {"marca": "jim", "categoria": "repasse", "origem": "cliente"}}`; mandar `"my payout did not arrive"` pela JIM; rollback com `POST /filas/versoes/{anterior}/ativar` (o número sai de `GET /filas/versoes`; a do seed costuma ser a 1, confira) | "A operação editou a fila sem deploy. A validação recusa valor errado. A próxima conversa já caiu na fila nova, e o registro de decisão mostra a versão e a regra. Rollback é reativar a anterior." |
| 1:50 a 2:50 | `GET /supervisor/metricas` (outbox por status) | `docker compose stop broker`; mandar 2 ou 3 mensagens; mostrar `outbox` com `pendente`; ~30 s depois `docker compose start broker`; mostrar a fila drenando; reenviar `POST /mensagens` com o mesmo `id_externo` e mostrar `"duplicada": true` | "Com o broker fora, nada se perde: o evento está na outbox, gravado junto com o estado. O relay tenta de novo com espera crescente, então pode levar algumas dezenas de segundos para sair. O prazo do agente não começou, porque só nasce no ack do broker. Se alguma resposta estava em voo, ela escala por timeout e aparece como escala, não como perda. O reenvio do canal vira uma mensagem só." |
| 2:50 a 3:50 | Painel do analista | `POST http://localhost:8200/modo {"modo": "lento"}`; mandar uma mensagem; esperar ~30 s; `GET /painel/atendentes` (pegar um humano da marca); `GET /painel/fila?marca=infinitepay`; `POST /painel/conversas/{id}/assumir {"id_atendente": "..."}`; `POST /painel/conversas/{id}/responder {...}`; mostrar `evento_descartado` na auditoria; voltar com `POST http://localhost:8200/modo {"modo": "normal"}` | "O agente passou dos 30 s; a conversa escalou com resumo de reserva, extrativo, e o cliente recebeu a transferência. O analista vê resumo, fontes e histórico. A resposta atrasada da IA chegou com a atribuição antiga e foi descartada: o fencing. Sem disjuntor, que ficou em Evolução, todas as conversas com a IA escalariam assim; por isso não há carga aqui." |
| 3:50 a 4:40 | Tabelas do experimento | `.venv\Scripts\python -m carga.tabelas`; `GET /supervisor/reconciliacao` | "Chave desligada contra ligada: duplicata no E3b e perda no E6 só com a chave desligada; p95 do E1 [preencher com o resultado]. Reconciliador zerado. Contado nas pontas, não pelo sistema." |
| 4:40 a 5:00 | Slide de limitações | — | "Mock com texto fixo, uma máquina a 50 msg/s e não 100, uma repetição, canais simulados, disjuntor e inatividade em Evolução. Tudo isso está no README com o efeito." |

Outros comandos úteis de `docs/api-front.md`, se pedirem: agente fora `{"modo": "fora"}` e duplicando `{"modo": "duplicar"}` em `http://localhost:8200/modo`; canal de saída fora `POST http://localhost:8310/modo {"modo": "fora"}`; fila de erros `GET /outbox/erros` e `POST /outbox/{id}/reprocessar`; devolver para a IA `POST /painel/conversas/{id}/devolver {"id_atendente": "...", "nota": "..."}`.
