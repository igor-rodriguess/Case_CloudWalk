# Pesquisa: diferenciais de IA, embeddings e arquiteturas de referência

Pesquisa de 2026-11-19 para a fase 2. Complementa `diferenciais.md` e `referencias.md` e não reabre o que já foi decidido.

**Como ler**
- Tipos de fonte: `[revisado]`, `[preprint]`, `[doc]`, `[mercado]`. Referências no texto como [n], numeradas na tabela da seção 5.
- Toda fonte da tabela foi aberta na web nesta pesquisa. A coluna "Conferido" diz o que eu vi: texto completo, resumo, documentação ou só resultado de busca e cobertura secundária.
- Cada número traz a origem (texto completo ou resumo). Número sem fonte é cálculo meu e vem marcado como tal.
- **Evidência** é o que a fonte diz. **Opinião** é julgamento meu: esforço, valor, desenho e recomendação.

---

## Resumo

### As 5 melhores apostas

Critério: valor para a avaliação (1 a 3) × força da evidência (1 a 3) ÷ esforço em dias. Valor = quanto pesa no que a banca avalia (triagem, handoff com contexto, auditoria, robustez, honestidade, demonstração). Evidência 3 = vários trabalhos revisados aplicáveis; 2 = revisado em contexto diferente ou preprint forte; 1 = só mercado. **Notas e dias são opinião.**

| # | Aposta | Valor | Evid. | Esforço | Nota |
|---|---|---|---|---|---|
| 1 | **Triagem com abstenção calibrada:** classificador + calibração + predição conforme; o incerto vai para triagem humana ou vira pergunta de esclarecimento | 3 | 3 | 4 d | 2,3 |
| 2 | **Escala proativa:** escore de risco ao vivo nas conversas com a IA e botão "assumir" para o humano, antes do gatilho automático | 3 | 2 | 3 d (com D4) | 2,0 |
| 3 | **Redação de dados pessoais** antes de embeddings, logs e avaliador | 2 | 2 | 2,5 d | 1,6 |
| 4 | **Banco de provas do agente:** replay em sombra pelo Kafka, pass^k e canário por fila | 3 | 2 | 4,5 d | 1,3 |
| 5 | **Juiz automático validado contra rótulos humanos (κ)** para priorizar a fila de qualidade (D2) | 2 | 3 | 5 d | 1,2 |

1. Atende a triagem com uma decisão auditável ("confiança baixa, foi para triagem humana"). Teoria madura e um trabalho revisado que aplica predição conforme a intenção em atendimento conversacional [5]. Roda em CPU com scikit-learn.
2. O maior experimento de campo sobre humano no circuito em atendimento (Alibaba, 680.676 conversas, texto completo) mostra que a escala emocional disparada por algoritmo, que chega tarde, foi a pior para a nota do cliente, e que a intervenção iniciada pelo humano, mais cedo, limitou o dano [15]. Reaproveita `transicionar` e o fencing por `id_atribuicao`.
3. Mostra LGPD no desenho (art. 6º, III) com pouco código. Há benchmark revisado em português com recall por tipo de dado [44].
4. O agente é de terceiros e muda. O help desk passa a certificar uma versão antes de dar tráfego, com o que já tem: Kafka relê eventos [43] e a IA é um atendente cadastrado, então duas versões viram dois atendentes.
5. Amplia D2 sem tratar o juiz como verdade: ele só ordena a revisão humana e só entra em critério com concordância medida. Evidência forte sobre vieses e validação [18–24]. Fica em 5º pelo custo de LLM e porque, com agente mock, só faz sentido com erros plantados.

Fora do top 5: detector de incidentes e copiloto (já decididos, aprofundados em 1.6 e 1.7); verificação de saída na fronteira com o agente (1.8, barata, candidata a 6º); roteamento por habilidade com aprendizado (1.9, não recomendado com dados sintéticos).

### Embeddings

**Opinião:** usar **Qwen3-Embedding-0.6B** (Apache 2.0, dimensão ajustável de 32 a 1024; melhor modelo multilíngue aberto em recuperação e reranking no MTEB-PT [58]), truncado para 512 ou 256 dimensões. Reserva para máquina fraca: **multilingual-e5-small** (MIT, 384 dimensões). **Não usar mmBERT cru:** é codificador de linguagem, não de frases; sem ajuste contrastivo fez 17,6 em recuperação no MTEB-PT, contra 78,9 do Qwen3-0.6B [58]. Confirmar com uma avaliação de um dia nos dados do projeto (2.5).

### O que contradiz ou corrige a arquitetura atual

1. **Brynjolfsson et al. está citado com números do working paper.** A versão QJE 2025 fala em 15% a mais de conversas resolvidas por hora; +14% e +34% são do NBER. A editora também registra pequena queda de qualidade entre os mais experientes [34]. Corrigir D5 em `diferenciais.md` e a entrada em `referencias.md`.
2. **Gatilho por sentimento negativo:** a intenção ("cedo, antes de piorar") confere com o estudo do Alibaba, mas o mecanismo não. No estudo, a escala emocional disparada por algoritmo chegou tarde e teve nota 0,928 menor que o atendimento só humano; a iniciada pelo humano teve 0,524 menor [15]. Um limiar de sentimento é reativo por natureza. Ver aposta 2. Os "680 mil" de `referencias.md` conferem (680.676).
3. **Filtro por marca com HNSW no pgvector:** o filtro roda depois da busca aproximada, então consultas com `marca` ou `id_cliente` podem voltar com menos linhas que o pedido [62]. Precisa de busca iterativa (0.8.0+) [63], índice parcial por marca ou busca exata quando o filtro deixa poucas linhas.
4. **Detector de incidente só por texto:** chamados do mesmo incidente costumam ter descrições diferentes; o iPACK só agregou bem cruzando texto com sinais do sistema [30]. Fundir o agrupamento com fila de erros, timeouts e categoria.
5. **Histórico completo em `conversa.atribuida`:** modelos usam mal informação no meio de contextos longos [71]. Enviar trechos escolhidos pela memória semântica e as últimas mensagens.
6. **Resumo do agente no handoff:** resumos abstrativos alucinam com frequência [72]. Mostrar o resumo com links para as mensagens de origem; o resumo de reserva extrativo é o mais seguro.
7. **Registro de decisão explicável e copiloto:** explicações aumentaram a aceitação de recomendações da IA inclusive quando ela errava [36]; viés de automação é documentado [37]. A explicação serve à auditoria; para o analista, mostrar confiança e fonte.
8. **Evolução "triagem com abstenção calibrada (Mozannar e Sontag)":** aprender a delegar exige decisões do especialista [11, 13], que não temos. Com dados sintéticos, o defensável é classificação seletiva com limiar (aposta 1).
9. **Contrato versionado sem tática de evolução:** estudo com 19 sistemas orientados a eventos lista cinco táticas [70]. Escolher e documentar uma.
10. **Usuários simulados por LLM não medem o agente** [42]. Experimento e banco de provas medem a plataforma, não a qualidade do atendimento.
11. **Lacuna em relação ao mercado:** a Intercom tem uma terceira saída além de resolver e escalar: a IA pede aprovação ou um dado ao humano e continua dona da conversa [65]. Nossa máquina de estados só escala.

---

## 1. Diferenciais de IA para o help desk

### 1.1 Triagem com abstenção calibrada (aposta 1)

**O que é.** A triagem preenche `categoria` (e, se valer, `prioridade`) com um classificador que também informa quanto confia. Com confiança baixa, a plataforma não chuta: manda para uma fila de triagem humana ou pede ao cliente para escolher entre as duas ou três categorias mais prováveis.

**Desenho (opinião)**
- Entrada: os embeddings da memória semântica ou TF-IDF. Modelo: regressão logística, treinada com conversas sintéticas rotuladas pelo gerador.
- Calibração no conjunto de validação (escala de temperatura ou Platt) [6, 7].
- Predição conforme dividida [3]: com nível α, o conjunto de categorias contém a verdadeira com probabilidade de pelo menos 1 − α, desde que os dados sejam permutáveis. Uma categoria: segue. Duas ou três: pergunta de esclarecimento, como no CICC [5]. Vazio ou grande: triagem humana.
- Para manter o roteador como função pura e os operadores atuais (`igual`, `diferente`, `em`), expor um campo derivado `faixa_confianca_triagem` (alta, media, baixa) em vez de um número. A fila "Triagem humana" com `faixa_confianca_triagem igual baixa` fica editável pela operação, sem operador novo.
- As regras atuais viram plano B. O registro de decisão guarda categoria, confiança, conjunto conforme, α e versão do modelo.
- LGPD art. 20 garante revisão de decisão só automatizada [46]; a fila humana e o registro são esse caminho.

**Evidência**
- Rejeitar abaixo de um limiar de confiança permite fixar o risco desejado [1]. Levantamento revisado separa rejeição por ambiguidade e por novidade [2].
- Predição conforme dá conjuntos com garantia de cobertura sem supor distribuição [3]; o controle conforme de risco estende a outras perdas [4].
- CICC (Findings NAACL 2024): predição conforme sobre classificador de intenção gera perguntas de esclarecimento pequenas que contêm a intenção certa no nível escolhido, em sete conjuntos, e trata pedidos fora de escopo [5] (resumo).
- Redes modernas saem mal calibradas; escala de temperatura resolve na maioria dos casos [6]. Com poucos dados, Platt supera regressão isotônica [7] (resumos).
- Fora do domínio, abster pela probabilidade do softmax funciona mal por excesso de confiança; um calibrador separado respondeu 56% das perguntas com 80% de acurácia, contra 48% usando só a probabilidade [8] (resumo).
- Modelos pequenos ajustados ainda superam LLMs com exemplos no prompt em classificação de texto, em 16 conjuntos [9]; SetFit ajusta modelos de frases com poucos exemplos [10] (resumos).
- O modelo de triagem da Uber decaiu com o tempo e passou a ser retreinado em ciclo fixo [14].

**Esforço (opinião).** 3 a 4 dias.

**Risco.** Acurácia otimista e circular em dados sintéticos. A garantia conforme quebra com deriva (categoria nova, incidente). Categoria mal definida vira ambiguidade permanente.

**Como medir.** Curva risco × cobertura (erro contra % triado automaticamente); erro de calibração e curva de confiabilidade; cobertura empírica no teste (perto de 1 − α); tamanho médio do conjunto; % para triagem humana. Teste de deriva: injetar uma categoria nova e mostrar a abstenção subir em vez de erro silencioso.

### 1.2 Escala proativa: risco ao vivo e humano que assume (aposta 2)

**O que é.** Cada conversa com a IA tem um escore de risco de falha, atualizado a cada mensagem. As de maior risco aparecem no painel do supervisor (D4) com um botão "assumir". Acima de um limiar alto, a escala é automática.

**Problema do case.** Requisitos 3, 6 e 7. Hoje a escala depende do agente, de timeout ou de sentimento negativo, e os três tendem a disparar tarde.

**Desenho (opinião)**
- Sinais baratos: número de turnos; cliente repetindo a pergunta (similaridade entre as próprias mensagens, com os embeddings já calculados); tendência do sentimento; pedido de humano; palavras de cancelamento; agente respondendo "não entendi"; categoria sensível; escalas anteriores do cliente (memória).
- Começa como regra pontuada; vira regressão logística quando o simulador gerar rótulos.
- "Assumir" é a transição `com_ia → com_humano` disparada por humano, motivo `assumida_proativamente`. O fencing por `id_atribuicao` já descarta a resposta atrasada da IA.
- O registro de decisão guarda o escore e os sinais no momento da escala.

**Evidência**
- Alibaba, experimento de campo randomizado, agosto de 2024, 647 atendentes, 680.676 conversas [15] (texto completo). Comparado a conversas só com humanos:
  - escala técnica disparada por algoritmo: duração +19,1%, qualidade preservada;
  - escala emocional disparada por algoritmo: duração +40,8%, novas tentativas +6 p.p., nota −0,928;
  - escala iniciada pelo humano: duração +9,5%, nota −0,524.
  Os autores atribuem a diferença ao momento: a escala emocional chega tarde, com sentimento negativo acumulado; a do humano chega cedo. Os supervisores já monitoravam as conversas da IA. Ressalva do texto: as conversas elegíveis para a IA eram menos de 10% do volume.
- MHCH (AAAI 2021) formaliza "quando transferir" como rótulo por mensagem, com métrica que aceita transferência um pouco adiantada [16] (resumo, sem números).
- IBM: atributos construídos a partir do conhecimento dos analistas previram escalas com recall de 87,36% e cortaram 88,23% do trabalho de achar chamados em risco, em 2,5 milhões de chamados [17] (resumo).
- Nubank (KDD 2026): o agente transfere quando sai da rotina, não acha o dado ou tem baixa confiança; detecção de frustração e escala proativa entraram em versões posteriores; limiares não publicados [24] (texto completo).

**Esforço (opinião).** 3 dias com D4 pronto; 5 sem ele.

**Risco.** O escore aprende o gerador sintético. Falso positivo sobrecarrega humanos. Generalização limitada: no Alibaba a IA cobria menos de 10% do volume; na CloudWalk, 75% (2023, `referencias.md`) a 90% (Gabriel, 2026, segundo a empresa [76]).

**Como medir.** Roteiros simulados que degradam num ponto conhecido: antecedência do alerta (turnos antes do ponto), precisão nas k primeiras posições da lista, falsos alarmes por hora, carga humana extra, tempo até o handoff com e sem escala proativa.

### 1.3 Redação de dados pessoais (aposta 3)

**O que é.** Uma etapa na Entrada troca CPF, CNPJ, telefone, e-mail, cartão, chave Pix e nomes por marcadores tipados e estáveis na conversa (`[CPF_1]`) antes de o texto ir para embeddings, logs, painel e juiz. O agente recebe o texto conforme a política de cada destino.

**Problema do case.** Os dados são sintéticos, mas a banca avalia coerência com a LGPD. Mostra o princípio da necessidade (art. 6º, III: "limitação do tratamento ao mínimo necessário") [46] na arquitetura, não só no README.

**Desenho (opinião).** Regex com validação (dígito verificador de CPF e CNPJ, Luhn no cartão) e NER em português (spaCy) para nomes. Política por destino numa tabela. O original fica só onde for necessário, com acesso auditado.

**Evidência**
- KDMiLe 2026, 996 boletins em português anotados por especialistas: pipeline local com regex e camada semântica. A configuração recomendada (qwen3:8b) teve recall de segurança de 0,966 e removeu de 99% a 100% de nomes, documentos, telefones e e-mails; o vazamento restante ficou em quase-identificadores de local. Os autores avisam que recall não mede risco de reidentificação [44] (resumo).
- Presidio combina NER, regex, regras e checksum, e o próprio projeto diz que não há garantia de achar todo dado sensível [45] (doc).

**Esforço (opinião).** 2 a 3 dias com regex e spaCy, sem LLM local.

**Risco.** Falsa sensação de anonimização; endereço em texto livre; vetores antigos calculados antes da redação.

**Como medir.** O gerador injeta PII em posições conhecidas: recall e precisão por tipo; varredura dos logs com os mesmos padrões (meta: zero); efeito da redação na busca semântica (recall@k antes e depois).

### 1.4 Banco de provas do agente (aposta 4)

**O que é.** Reexecuta conversas gravadas contra uma versão nova do agente sem tocar clientes e, aprovada, libera a versão para uma fração de uma fila.

**Problema do case.** O help desk é quem vê o efeito do agente no cliente. Pode exigir conformidade de contrato, latência e comportamento antes de dar tráfego. Também alimenta o experimento técnico.

**Desenho (opinião)**
- Cenário = conversa sintética gravada mais o resultado esperado (resolver; escalar com motivo X; ação Y).
- Modo sombra: tópico e grupo de consumidores próprios, saída por canal desligada, inbox e outbox com `consumidor = banco_de_provas`.
- Métricas por versão: falhas de JSON Schema, p95, taxa de escala, ações acima dos limites da persona (D1) e pass^k (o mesmo cenário k vezes).
- Canário: a versão B entra como outro atendente `tipo = ia`, com capacidade pequena numa fila. O distribuidor faz o resto.

**Evidência**
- τ-bench (ICLR 2025): agentes de ponta resolvem menos de 50% das tarefas e pass^8 fica abaixo de 25% no varejo [38] (resumo). τ²-bench: desempenho cai quando o usuário também age no ambiente [39] (resumo). CRMArena (NAACL 2025): menos de 40% das tarefas com ReAct e menos de 55% com chamada de função [40] (resumo).
- Avaliação de agentes deve reportar custo junto com acurácia e usar conjuntos de reserva [41] (resumo).
- Eventos do Kafka não são apagados ao serem consumidos e podem ser lidos quantas vezes for preciso, dentro da retenção do tópico [43] (doc).
- DoorDash: simulador com cliente feito por LLM, APIs de backend simuladas e juízes calibrados contra humanos, em ciclo contínuo [68] (cobertura secundária).
- Contra: usuários simulados variam a taxa de sucesso do mesmo agente em até 9 p.p. conforme o LLM do usuário, subestimam em tarefas difíceis e superestimam nas médias [42] (resumo).

**Esforço (opinião).** 4 a 5 dias.

**Risco.** Com o mock, mede-se a plataforma, não o agente. Replay sem o estado do backend diverge. Efeito externo vazando do modo sombra.

**Como medir.** Mock B com regressões plantadas (esquema quebrado, escala em excesso, latência, ação acima do limite): % detectada antes do canário; tempo para certificar uma versão.

### 1.5 Juiz automático validado na fila de qualidade (aposta 5)

**O que é.** Extensão de D2. Um LLM avalia cada conversa resolvida pela IA com rubrica binária por critério e ordena a fila de revisão humana. O humano continua decidindo.

**Desenho (opinião)**
- Critérios binários: resposta correta; tom da marca; deveria ter escalado; vazou dado. O Nubank usou passa/falha nos cinco avaliadores [24].
- Rotular à mão de 100 a 200 conversas antes de fixar a rubrica, porque os critérios mudam enquanto se corrige [22].
- κ juiz × humano por critério; o juiz só entra nos critérios que passarem de um limiar definido antes.
- Juiz de família diferente da do agente [20]; ordem trocada ao comparar duas respostas [19].
- Amostra estratificada por categoria e risco, em vez de sorteio uniforme.
- Com o mock, plantar erros conhecidos (resposta errada, tom errado, não escalou) para ter gabarito.

**Evidência**
- GPT-4 como juiz passou de 80% de concordância com humanos, nível parecido com humano × humano, com vieses de posição, verbosidade e autopromoção [18] (resumo).
- Trocar a ordem das respostas muda o veredito; calibrar pela posição reduz o viés [19] (resumo).
- Juízes reconhecem e favorecem o próprio texto [20] (resumo).
- Só os juízes maiores se alinham razoavelmente a humanos e ainda erram até 5 pontos; % de concordância engana, κ discrimina melhor; há viés de leniência [21] (resumo).
- Em 150 mil interações de e-commerce, juízes seguiram a tendência de satisfação mas perderam nuances da insatisfação; os autores recomendam vários juízes mais feedback do usuário [23] (resumo).
- Nubank (KDD 2026, texto completo) [24]: 2.130 exemplos rotulados por três analistas com voto da maioria. Com o prompt inicial, o κ entre modelos foi desprezível em vários pares (exemplo: 0,00); depois de otimizar o prompt, a maioria passou de 0,7. A acurácia contra humanos chegou a 73% a 89% conforme o avaliador. Não reportam concordância humano × humano.
- DoorDash: juiz em cinco dimensões e guardrail em dois níveis; redução de 90% nas alucinações, número da própria empresa [67] (só resumos; o post bloqueou acesso).

**Esforço (opinião).** 4 a 6 dias, mais custo de API ou máquina para modelo local.

**Risco.** Circularidade com o mock; custo; juiz tratado como verdade.

**Como medir.** κ por critério; recall dos erros plantados; custo por conversa; taxa de veredito invertido ao trocar a ordem.

### 1.6 Detector de incidentes (decidido; aprofundamento)

**Desenho (opinião)**
1. Agrupamento incremental: a mensagem entra no grupo cujo centróide recente passa de um limiar de cosseno, ou abre um grupo novo. É a detecção de evento novo da linha TDT [25, 26]. No nosso volume não precisa do LSH de [26]; o pgvector basta.
2. Rajada por grupo e por categoria: CUSUM sobre a contagem por janela [28]; o modelo de rajadas de Kleinberg [27] se sobrar tempo.
3. Fusão com sinais do sistema: fila de erros, `timeout_agente`, `falha_integracao`, escalas por categoria.
4. Ação: registro de incidente que agrupa conversas, alerta o supervisor e sugere uma fila temporária (regra nova versionada, ativada por humano).

**Evidência.** No iPACK (ICSE 2023, Azure), chamados duplicados do mesmo incidente tinham descrições diferentes; cruzar chamados com alertas da nuvem deu F1 de 0,871 a 0,935 [30] (resumo). BERTopic agrupa com HDBSCAN em lote [29]: serve para rotular grupos depois, não para detectar ao vivo.

**Como medir.** Incidente sintético com paráfrases variadas em PT e EN no meio do tráfego normal: atraso de detecção, falsos alarmes por dia, pureza dos grupos.

### 1.7 Copiloto do analista (D5; aprofundamento)

- LinkedIn (SIGIR 2024): recuperação sobre um grafo de chamados passados, em uso por cerca de seis meses, reduziu em 28,6% o tempo mediano de resolução por chamado; +77,6% em MRR [35] (resumo). Sustenta somar "casos parecidos já resolvidos" (memória semântica) ao rascunho.
- Brynjolfsson et al.: na versão QJE, 15% a mais de conversas resolvidas por hora; ganho de velocidade e qualidade para os menos experientes; pequeno ganho de velocidade e pequena queda de qualidade para os mais experientes [34].
- Explicação aumenta aceitação mesmo quando a IA erra [36]; o viés de automação depende de confiança, carga e pressão de tempo [37] (resumos).
- **Opinião:** mostrar fonte e confiança na sugestão; medir a aceitação sem edição de sugestões erradas plantadas.

### 1.8 Verificação de saída na fronteira com o agente (candidata a 6º)

- **O que é:** antes de `mensagem.enviada` entrar na outbox do canal, regras determinísticas checam os limites da persona (valor máximo, promessas proibidas, dado de outro cliente). Violação: segura a mensagem e escala com motivo `violacao_politica`.
- **Evidência:** a DoorDash checa cada resposta antes do usuário e cai para humano quando preciso [67] (só resumos). A Air Canada foi responsabilizada pelo que o chatbot disse [75] (cobertura jurídica). O Nubank mantém crédito, dívida e limite sob supervisão humana [24].
- **Esforço (opinião):** 2 dias. Medir com violações plantadas no mock.

### 1.9 Roteamento por habilidade com aprendizado (não recomendado agora)

- **Evidência:** rotear por desempenho individual cria uma fronteira entre espera e resolução [31] (resumo); roteamento de chamados por sequência de resolução funciona com histórico real [32]; avaliar política aprendida fora de produção exige log com exploração aleatória [33] (resumo).
- **Opinião:** com analistas sintéticos, a "habilidade" aprendida é parâmetro do gerador. Registrar resultado por atendente e categoria agora; aprendizado fica como evolução.

### 1.10 Quando escalar: aprender a delegar

- **Evidência:** Mozannar e Sontag [11] e Madras et al. [12] tratam a delegação como decisão aprendida que leva em conta o especialista. Hemmer et al. reduzem, mas não eliminam, a necessidade de previsões do especialista [13].
- **Opinião:** sem decisões humanas reais, fica como evolução. A aposta 1 entrega o comportamento observável (abster e mandar ao humano) com garantia mais simples de defender.

---

## 2. Embeddings para PT e EN

### 2.1 Requisitos (opinião)

Local e em CPU; PT e EN com um modelo só; licença livre; até 2.000 dimensões para indexar `vector` com HNSW [62]; armazenamento compatível com 600 mil mensagens por dia no estresse.

Memória e busca são sempre filtradas por marca, e cada marca tem uma língua. Quase não há busca entre línguas: o requisito é qualidade em cada língua, não alinhamento PT↔EN.

### 2.2 mmBERT (arXiv 2509.06888)

**Evidência** [47, 48]
- Codificador treinado só com modelagem de linguagem mascarada, 3T tokens, mais de 1.800 línguas. Base: 307M parâmetros (110M fora dos embeddings), 768 dimensões. Small: 140M (42M), 384 dimensões. Contexto até 8.192 tokens. Tokenizador do Gemma 2. Licença MIT (cartão do modelo).
- Os autores ajustaram todos os modelos no MS MARCO (1,25M triplas, uma época, SentenceTransformers) antes de medir recuperação. Assim, o base fez 54,1 no MTEB v2 multilíngue, contra 52,4 do XLM-R (texto completo). Não há modelo de frases oficial.
- No MTEB-PT, o mmbert-base sem ajuste fez 17,6 em recuperação e 59,4 em STS; um ajuste da comunidade (mmbert-embed-32k) fez 67,3 e 76,4 [58] (texto completo).

**O que seria preciso para usá-lo em similaridade de frases**
1. Ajuste contrastivo no estilo SBERT [49]: pares ou triplas (consulta, positivo, negativo difícil), pooling por média.
2. Dados do domínio em PT e EN. No MTEB-PT, o ajuste contrastivo em português ajudou muito em STS, mas piorou outras tarefas em alguns casos: o e5-large perdeu 2,7 pontos em recuperação e o bertimbau perdeu 14,2 em reranking (cálculo sobre a tabela 3 de [58]).
3. GPU para o ajuste e uma avaliação própria.

**Opinião:** não cabe no mês, e o ponto de partida perde para modelos prontos. Fica como evolução se houver dados reais da CloudWalk para o ajuste.

### 2.3 Alternativas prontas

| Modelo | Parâm. | Dim. | Contexto | Licença | Observação | Fonte |
|---|---|---|---|---|---|---|
| Qwen3-Embedding-0.6B | 0,6B | 1024 (32 a 1024, MRL) | 32K | Apache 2.0 | consulta leva instrução; sem ela, perda de 1% a 5% segundo o cartão; transformers 4.51+ | [53] |
| EmbeddingGemma-300m | 308M | 768 (512, 256, 128) | 2.048 | Gemma (acesso com aceite) | prompt por tarefa; sem float16 | [54] |
| multilingual-e5-small | 12 camadas | 384 | 512 | MIT | prefixos `query: ` e `passage: ` obrigatórios | [51, 55] |
| multilingual-e5-large-instruct | 560M | não conferido | não conferido | não conferida | melhor modelo público do MMTEB [57] | [51, 57] |
| BGE-M3 | 568M | não conferido | 8.192 | não conferida | denso, esparso e multivetor | [52] |
| gte-multilingual-base | 305M | não conferido | não conferido | não conferida | | [54, 58] |
| paraphrase-multilingual-MiniLM-L12-v2 | não conferido | não conferido | não conferido | não conferida | destilação multilíngue [50]; pior média do MTEB-BR | [59] |

MRL (Matryoshka) permite truncar o vetor mantendo as primeiras dimensões úteis [60].

### 2.4 Benchmarks

- MTEB: nenhum método domina todas as tarefas [56]. MMTEB: mais de 500 tarefas em mais de 250 línguas [57] (resumos).
- O ranking global prevê o ranking em português só moderadamente (Spearman 0,75 em 55 modelos) [59]; nenhum modelo domina todas as tarefas em português [58].

**MTEB-PT** (BRACIS 2026, tabela 3, texto completo) [58]

| Modelo | STS | Classif. | Recup. | Rerank. |
|---|---|---|---|---|
| qwen3-embedding-0.6b | 80,7 | 52,3 | **78,9** | **85,8** |
| gte-multilingual-base | 80,4 | 50,2 | 76,9 | 84,2 |
| multilingual-e5-large-instruct | 81,3 | 53,0 | 70,1 | 84,5 |
| multilingual-e5-base | 76,9 | 49,1 | 71,7 | 84,5 |
| multilingual-e5-small | 76,9 | 49,3 | 70,2 | 84,0 |
| multilingual-mpnet-base | 78,7 | 50,6 | 58,0 | 81,1 |
| mmbert-embed-32k (comunidade) | 76,4 | 49,5 | 67,3 | 82,7 |
| mmbert-base (sem ajuste) | 59,4 | 48,0 | 17,6 | 70,3 |
| text-embedding-3-large (API) | 79,1 | 56,3 | 91,1* | 82,0 |

\* Modelos fechados rodaram recuperação em só 20% de um dos conjuntos. EmbeddingGemma não foi avaliado.

**MMTEB v2 multilíngue**, média por tarefa (tabela 5 do artigo do EmbeddingGemma, texto completo) [54]: Qwen3-Embedding-0.6B 64,34; mE5-large-instruct 63,22; EmbeddingGemma 61,15; BGE-M3 59,56; Jina v3 58,37; GTE multilingual base 58,24. Ressalva: artigo do próprio fabricante.

**MTEB-BR** (preprint de autor único, 93 modelos, texto completo lido em parte) [59]: EmbeddingGemma-300m 0,6490 (13º), mE5-large-instruct 0,641 (19º), paraphrase-multilingual-MiniLM-L12-v2 0,248 (a pior). Não achei nota do Qwen3-0.6B no trecho lido.

### 2.5 Recomendação e como decidir (opinião)

1. **Principal: Qwen3-Embedding-0.6B**, truncado para 512 (ou 256) e renormalizado. Melhor modelo multilíngue aberto em recuperação e reranking no MTEB-PT, que é revisado [58] (em recuperação, só um modelo só-português ajustado pelos próprios autores passa dele: 81,1, com reranking de 62,3); topo do MMTEB entre os pequenos [54]; Apache 2.0; MRL reduz armazenamento.
2. **Reserva para CPU fraca: multilingual-e5-small.** Perde 8,7 pontos em recuperação no MTEB-PT (70,2 contra 78,9) [58].
3. **EmbeddingGemma-300m** é meio-termo competitivo (13º no MTEB-BR), mas a licença Gemma exige aceite.
4. **Evitar** mmBERT sem ajuste e paraphrase-multilingual-MiniLM.

**Avaliação de um dia nos dados do projeto**
- De 200 a 300 mensagens sintéticas por língua, com intenção conhecida e paráfrases. Se geradas por LLM, usar família diferente das candidatas (hipótese: reduz favorecimento).
- Medir: recall@5 de "mesma intenção" (casos parecidos), V-measure do agrupamento (detector), acurácia de regressão logística sobre os vetores (aposta 1), latência p95 por lote e memória na máquina de desenvolvimento.
- Regra: o menor modelo a até 2 pontos do melhor em recall@5. O limiar é arbitrário; declarar no README.

### 2.6 Notas de operação

- Calcular embeddings fora do caminho crítico, num consumidor do log de eventos, nunca dentro de `transicionar`. O teste de 100 msg/s não depende do modelo.
- Guardar `modelo_embedding` e `dimensao` em cada vetor. Trocar de modelo exige recalcular tudo; vetores de modelos diferentes não são comparáveis.
- Com vetores normalizados, o README do pgvector recomenda produto interno (`<#>`) pelo desempenho [62].
- Armazenamento (cálculo meu, com a fórmula `4 × dimensões + 8` bytes [62]): 1024 dimensões ≈ 4,1 KB por vetor, ≈ 2,5 GB por dia com 600 mil mensagens; com 256 dimensões, ≈ 0,6 GB por dia. Vetorizar só mensagens do cliente e um resumo por conversa reduz mais.
- Filtro com HNSW: roda depois da busca. Com `ef_search` padrão (40) e um filtro que casa 10% das linhas, voltam cerca de 4 linhas em média [62]. Usar `hnsw.iterative_scan` (pgvector 0.8.0+) [63], índice parcial por marca ou busca exata quando o filtro deixa poucas linhas (histórico de um cliente).
- Cosseno de embeddings aprendidos pode dar valores arbitrários quando o treino não otimiza cosseno; um dos remédios propostos é treinar direto com objetivo de cosseno [61]. **Opinião:** modelos de frases treinados de forma contrastiva seguem esse remédio; mais um motivo para não usar mmBERT cru.

---

## 3. Arquiteturas de referência

### 3.1 O que o mercado e a literatura mostram

- **Bot como atendente com handoff por status** (Chatwoot): o bot passa a conversa de `pending` para `open`; o humano pode devolver [66].
- **"Quando" separado de "para onde"** (Intercom): regras determinísticas (atributos como sentimento, tipo de problema, dados do cliente e de conectores) e orientação em linguagem natural decidem quando escalar; workflows decidem para onde vai [64].
- **Terceira saída** (Intercom, "Ask for input"): a IA segura a resposta, pede aprovação, um dado ou uma decisão ao humano e segue com a conversa. O humano aprova, responde ou assume; um timeout decide se não houver resposta [65].
- **Supervisão ao vivo com intervenção proativa** (Alibaba) [15].
- **Guardrail antes de enviar, juiz de qualidade, simulação contínua, queda para humano** (DoorDash) [67, 68].
- **Avaliação dirigida por juízes validados; decisões reguladas com humano** (Nubank) [24].
- **Copiloto com recuperação de casos passados** (LinkedIn) [35].
- **Começar simples:** workflows antes de agentes, checkpoints humanos, testes em sandbox (Anthropic) [69].
- **Contexto CloudWalk:** o agente Gabriel fecha 90% dos casos sem humano, segundo a empresa, e leva o cliente a um especialista quando o caso pede julgamento, empatia ou decisão operacional. Sem detalhe de arquitetura [76].

### 3.2 Onde a nossa arquitetura difere

| Padrão | Referência | Nós hoje | Leitura (opinião) |
|---|---|---|---|
| IA como atendente, handoff por status | Chatwoot [66] | igual | manter |
| "Quando" separado de "para onde" | Intercom [64] | gatilhos de escala separados do roteador | manter; deixar explícito na doc |
| IA consulta o humano e continua dona | Intercom [65] | não existe; só escala | adotar (3.3) |
| Supervisor acompanha e assume cedo | Alibaba [15] | só escala por gatilho | aposta 2 |
| Checagem da resposta antes de enviar | DoorDash [67]; Air Canada [75] | não existe na plataforma | 1.8 |
| Simulação e avaliação contínua | DoorDash [68]; Nubank [24]; τ-bench [38] | experimento mede só robustez | aposta 4 |
| Juiz calibrado contra humano | Nubank [24]; DoorDash [68] | D2 manual | aposta 5 |
| Copiloto com casos passados | LinkedIn [35]; QJE [34] | D5 | manter; somar casos parecidos com fonte |
| Decisões reguladas ficam com humano | Nubank [24] | limites de ação na persona (D1) | manter; ligar a filas só humanas |
| Eventos retidos e reprocessáveis | Kafka [43] | Kafka como transporte | usar para replay (aposta 4) |
| Evolução de esquema de eventos | Overeem et al. [70] | "versionamento" sem tática | escolher tática (3.3) |
| Estado em tabelas + log de auditoria | Overeem et al. [70] descreve as dores de evoluir sistemas só de eventos | estado em tabelas, eventos para auditoria e integração | manter; evita a parte mais difícil do event sourcing |

### 3.3 O que adotar (opinião, em ordem)

1. **Escala proativa e lista de risco** (aposta 2).
2. **Consulta ao humano:** eventos `consulta.solicitada` e `consulta.respondida` no contrato 1.1, subestado `com_ia_aguardando_humano` e timeout no agendador. Dá ao agente uma saída mais barata que escalar. 2 a 3 dias.
3. **Verificação de saída** (1.8).
4. **Tática de evolução do contrato:** eventos versionados mais conversão para a versão nova no consumidor (upcasting), duas das cinco táticas de [70]; mudança só aditiva dentro da mesma versão maior.
5. **Banco de provas** (aposta 4).

---

## 4. Riscos e críticas que tocam escolhas nossas

| Escolha | Crítica | Fonte | Mitigação (opinião) |
|---|---|---|---|
| IA first, automação alta | 64% dos clientes preferem que empresas não usem IA no atendimento; 60% temem não conseguir falar com uma pessoa (Gartner, 5.728 clientes, dez/2023, comunicado) | [73] | caminho para humano sempre disponível (gatilho de pedido explícito, já previsto); medir satisfação por tipo de atendente |
| IA first, automação alta | Klarna voltou a contratar humanos em 2025; o CEO disse que custo pesou demais e a qualidade caiu (cobertura da entrevista à Bloomberg) | [74] | idem |
| IA first, automação alta | No Alibaba, conversas da IA sem escala tiveram nota 0,858 menor que as só humanas, com novas tentativas iguais; os autores atribuem ao estilo de comunicação | [15] | persona por marca (D1) e fila de qualidade (D2) |
| Gatilho por sentimento negativo | escala emocional por algoritmo chega tarde e é a pior | [15] | aposta 2 |
| Resumo do agente no handoff | resumos abstrativos alucinam com frequência | [72] | links para as mensagens de origem; resumo extrativo de reserva |
| Histórico em `conversa.atribuida` | informação no meio de contexto longo é mal usada | [71] | trechos da memória semântica e últimas mensagens |
| Registro explicável, copiloto | explicação aumenta aceitação do erro; viés de automação | [36, 37] | mostrar confiança e fonte; medir aceitação de sugestão errada |
| Memória e incidentes por cosseno | cosseno pode ser arbitrário em certos treinos; texto sozinho não agrupa o mesmo incidente | [61, 30] | modelo contrastivo; fundir com sinais do sistema |
| pgvector com filtro por marca | filtro depois do HNSW devolve menos linhas | [62, 63] | busca iterativa, índice parcial, busca exata |
| Dados sintéticos | usuários simulados não representam humanos; política aprendida exige exploração real | [42, 33] | afirmar só robustez da plataforma; declarar nas limitações |
| Triagem com conformal | garantia supõe permutabilidade; modelo decai; softmax superconfiante fora do domínio | [3, 14, 8] | monitorar cobertura; retreino; teste de deriva |
| Juiz automático | posição, verbosidade, autopromoção, leniência, nuance perdida | [18–23] | κ por critério, ordem trocada, juiz de outra família, humano decide |
| Contrato versionado | evolução de esquema é a dor principal em sistemas de eventos | [70] | tática explícita (3.3) |
| Agente de terceiros | a empresa responde pelo que o bot diz | [75] | auditoria (já prevista) e verificação de saída (1.8) |
| Números do copiloto | QJE: 15%; 14% e 34% são do working paper | [34] | corrigir docs |

---

## 5. Fontes

Conferido: **TC** = texto completo; **R** = resumo ou página do artigo; **D** = documentação lida; **B** = só resultado de busca ou cobertura secundária.

| # | Fonte | Autores | Venue, ano | Tipo | URL | Conferido |
|---|---|---|---|---|---|---|
| 1 | Selective Classification for Deep Neural Networks | Geifman, El-Yaniv | NeurIPS 2017 | `[revisado]` | https://papers.nips.cc/paper_files/paper/2017/file/4a8423d5e91fda00bb7e46540e2b0cf1-Paper.pdf | R |
| 2 | Machine Learning with a Reject Option: A Survey | Hendrickx, Perini, Van der Plas, Meert, Davis | Machine Learning 113, 2024 | `[revisado]` | https://arxiv.org/abs/2107.11277 | R |
| 3 | Conformal Prediction: A Gentle Introduction | Angelopoulos, Bates | Foundations and Trends in ML 16(4), 2023 | `[revisado]` | https://nowpublishers.com/article/Details/MAL-101 | R |
| 4 | Conformal Risk Control | Angelopoulos, Bates, Fisch, Lei, Schuster | ICLR 2024 | `[revisado]` | https://proceedings.iclr.cc/paper_files/paper/2024/hash/f3549ef9b5ff520a7e41ff3cc306ab2b-Abstract-Conference.html | R |
| 5 | Conformal Intent Classification and Clarification for Fast and Accurate Intent Recognition | den Hengst, Wolter, Altmeyer, Kaygan | Findings of NAACL 2024 | `[revisado]` | https://aclanthology.org/2024.findings-naacl.156 | R |
| 6 | On Calibration of Modern Neural Networks | Guo, Pleiss, Sun, Weinberger | ICML 2017 | `[revisado]` | https://proceedings.mlr.press/v70/guo17a.html | R |
| 7 | Predicting Good Probabilities with Supervised Learning | Niculescu-Mizil, Caruana | ICML 2005 | `[revisado]` | https://mlanthology.org/icml/2005/niculescumizil2005icml-predicting | R |
| 8 | Selective Question Answering under Domain Shift | Kamath, Jia, Liang | ACL 2020 | `[revisado]` | https://arxiv.org/abs/2006.09462 | R |
| 9 | Language Models for Text Classification: Is In-Context Learning Enough? | Edwards, Camacho-Collados | LREC-COLING 2024 | `[revisado]` | https://aclanthology.org/2024.lrec-main.879 | R |
| 10 | Efficient Few-Shot Learning Without Prompts (SetFit) | Tunstall, Reimers, Jo, Bates, Korat, Wasserblat, Pereg | arXiv 2022 | `[preprint]` | https://arxiv.org/abs/2209.11055 | R |
| 11 | Consistent Estimators for Learning to Defer to an Expert | Mozannar, Sontag | ICML 2020 | `[revisado]` | https://proceedings.mlr.press/v119/mozannar20b.html | R |
| 12 | Predict Responsibly: Improving Fairness and Accuracy by Learning to Defer | Madras, Pitassi, Zemel | NeurIPS 2018 | `[revisado]` | https://proceedings.neurips.cc/paper/2018/hash/09d37c08f7b129e96277388757530c72-Abstract.html | R |
| 13 | Learning to Defer with Limited Expert Predictions | Hemmer, Thede, Vössing, Jakubik, Kühl | AAAI 2023 | `[revisado]` | https://ojs.aaai.org/index.php/AAAI/article/view/25742 | R |
| 14 | Scaling Uber's Customer Support Ticket Assistant (COTA) System with Deep Learning | Somasundaram, Hermann, Williams et al. | Uber Engineering, 2018 | `[mercado]` | https://www.uber.com/blog/cota-v2/ | TC |
| 15 | Agentic AI and Human-in-the-Loop Interventions: Field Experimental Evidence from Alibaba's Customer Service Operations | Wang, Zhu, Feng, Lu, Jia | arXiv 2605.14830, 2026 | `[preprint]` | https://arxiv.org/abs/2605.14830 | TC (PDF) |
| 16 | Time to Transfer: Predicting and Evaluating Machine-Human Chatting Handoff | Liu, Gao, Kang, Jiang, He, Sun, Liu, Lu | AAAI 2021 | `[revisado]` | https://ojs.aaai.org/index.php/AAAI/article/view/16731 | R |
| 17 | Customer Support Ticket Escalation Prediction using Feature Engineering | Montgomery, Damian, Bulmer, Quader | Requirements Engineering (Springer), DOI 10.1007/s00766-018-0297-y | `[revisado]` | https://arxiv.org/abs/2010.06145 | R |
| 18 | Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena | Zheng et al. | NeurIPS 2023 (Datasets and Benchmarks) | `[revisado]` | https://arxiv.org/abs/2306.05685 | R |
| 19 | Large Language Models are not Fair Evaluators | Wang, P. et al. | ACL 2024 | `[revisado]` | https://aclanthology.org/2024.acl-long.511 | R |
| 20 | LLM Evaluators Recognize and Favor Their Own Generations | Panickssery, Bowman, Feng | NeurIPS 2024 | `[revisado]` | https://papers.nips.cc/paper_files/paper/2024/hash/7f1f0218e45f5414c79c0679633e47bc-Abstract-Conference.html | R |
| 21 | Judging the Judges: Evaluating Alignment and Vulnerabilities in LLMs-as-Judges | Thakur, Choudhary, Ramayapally, Vaidyanathan, Hupkes | GEM² Workshop (ACL), 2025 | `[revisado]` | https://aclanthology.org/2025.gem-1.33 | R |
| 22 | Who Validates the Validators? Aligning LLM-Assisted Evaluation of LLM Outputs with Human Preferences | Shankar, Zamfirescu-Pereira, Hartmann, Parameswaran, Arawjo | UIST 2024 | `[revisado]` | https://arxiv.org/abs/2404.12272 | R |
| 23 | Whom to Trust? Analyzing the Divergence Between User Satisfaction and LLM-as-a-Judge in E-Commerce RAG Systems | Türkmen, Keleş | MME Workshop (ACL), 2026 | `[revisado]` | https://aclanthology.org/2026.mme-main.12/ | R |
| 24 | Building Customer Support AI Agents at 100M-User Scale: An Evaluation-Driven Framework | Gupta et al. (Nubank) | KDD 2026 (aceito, segundo o arXiv) | `[revisado]` | https://arxiv.org/abs/2606.08867 | TC (HTML) |
| 25 | On-Line New Event Detection and Tracking | Allan, Papka, Lavrenko | SIGIR 1998 | `[revisado]` | https://doi.org/10.1145/290941.290954 | B (registro bibliográfico) |
| 26 | Streaming First Story Detection with application to Twitter | Petrović, Osborne, Lavrenko | NAACL 2010 | `[revisado]` | https://aclanthology.org/N10-1021 | R |
| 27 | Bursty and Hierarchical Structure in Streams | Kleinberg | KDD 2002 | `[revisado]` | https://doi.org/10.1145/775047.775061 | R |
| 28 | Continuous Inspection Schemes | Page | Biometrika 41(1-2), 1954 | `[revisado]` | https://doi.org/10.1093/biomet/41.1-2.100 | B (registro bibliográfico) |
| 29 | BERTopic: Neural topic modeling with a class-based TF-IDF procedure | Grootendorst | arXiv 2022 | `[preprint]` | https://arxiv.org/abs/2203.05794 | R |
| 30 | Incident-aware Duplicate Ticket Aggregation for Cloud Systems (iPACK) | Liu, J. et al. | ICSE 2023 | `[revisado]` | https://arxiv.org/abs/2302.09520 | R |
| 31 | Routing to Manage Resolution and Waiting Time in Call Centers with Heterogeneous Servers | Mehrotra, Ross, Ryder, Zhou | MSOM 14(1), 2012 | `[revisado]` | https://doi.org/10.1287/msom.1110.0349 | R |
| 32 | Efficient Ticket Routing by Resolution Sequence Mining | Shao, Chen, Tao, Yan, Anerousis | KDD 2008 | `[revisado]` | https://doi.org/10.1145/1401890.1401964 | R |
| 33 | A Contextual-Bandit Approach to Personalized News Article Recommendation | Li, Chu, Langford, Schapire | WWW 2010 | `[revisado]` | https://arxiv.org/abs/1003.0146 | R |
| 34 | Generative AI at Work | Brynjolfsson, Li, Raymond | QJE 140(2), 2025; DOI 10.1093/qje/qjae044 | `[revisado]` | https://www.eurekalert.org/news-releases/1071936 | D (comunicado da editora); WP NBER por B |
| 35 | Retrieval-Augmented Generation with Knowledge Graphs for Customer Service Question Answering | Xu, Cruz, Guevara, Wang, Deshpande, Wang, Li | SIGIR 2024 | `[revisado]` | https://arxiv.org/abs/2404.17723 | R |
| 36 | Does the Whole Exceed its Parts? The Effect of AI Explanations on Complementary Team Performance | Bansal, Wu, Zhou, Fok, Nushi, Kamar, Ribeiro, Weld | CHI 2021 | `[revisado]` | https://arxiv.org/abs/2006.14779 | R |
| 37 | Automation bias: a systematic review of frequency, effect mediators, and mitigators | Goddard, Roudsari, Wyatt | JAMIA 19(1), 2012 | `[revisado]` | https://pmc.ncbi.nlm.nih.gov/articles/PMC3240751 | R |
| 38 | τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains | Yao, Shinn, Razavi, Narasimhan | ICLR 2025 | `[revisado]` | https://arxiv.org/abs/2406.12045 | R |
| 39 | τ²-Bench: Evaluating Conversational Agents in a Dual-Control Environment | Barres, Dong, Ray, Si, Narasimhan | arXiv 2025 | `[preprint]` | https://arxiv.org/abs/2506.07982 | R |
| 40 | CRMArena: Understanding the Capacity of LLM Agents to Perform Professional CRM Tasks in Realistic Environments | Huang, Prabhakar, Dhawan, Mao, Wang, Savarese, Xiong, Laban, Wu | NAACL 2025 | `[revisado]` | https://arxiv.org/abs/2411.02305 | R |
| 41 | AI Agents That Matter | Kapoor, Stroebl, Siegel, Nadgir, Narayanan | TMLR 2025 | `[revisado]` | https://arxiv.org/abs/2407.01502 | R |
| 42 | Lost in Simulation: LLM-Simulated Users are Unreliable Proxies for Human Users in Agentic Evaluations | Seshadri, Cahyawijaya, Odumakinde, Singh, Goldfarb-Tarrant | ACL 2026 | `[revisado]` | https://aclanthology.org/2026.acl-long.2192/ | R |
| 43 | Apache Kafka: Introduction | Apache Software Foundation | documentação | `[doc]` | https://kafka.apache.org/intro | D |
| 44 | Local Anonymization of Free-Text Robbery Police Reports in Brazilian Portuguese: a Safety-Recall-Oriented Multi-Model Benchmark | de Almeida, Botega, Lima | KDMiLe 2026 (SBC) | `[revisado]` | https://sol.sbc.org.br/index.php/kdmile/article/view/44984 | R |
| 45 | Presidio (README) | Microsoft / data-privacy-stack | documentação | `[doc]` | https://github.com/microsoft/presidio | D |
| 46 | Lei 13.709/2018 (LGPD), arts. 6º, 12 e 20 | Brasil | lei | `[doc]` | https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm | D |
| 47 | mmBERT: A Modern Multilingual Encoder with Annealed Language Learning | Marone, Weller, Fleshman, Yang, Lawrie, Van Durme | arXiv 2509.06888, 2025 | `[preprint]` | https://arxiv.org/abs/2509.06888 | TC (HTML) |
| 48 | jhu-clsp/mmBERT-base (cartão do modelo) | JHU CLSP | Hugging Face | `[doc]` | https://huggingface.co/jhu-clsp/mmBERT-base | D |
| 49 | Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks | Reimers, Gurevych | EMNLP-IJCNLP 2019 | `[revisado]` | https://aclanthology.org/D19-1410/ | R |
| 50 | Making Monolingual Sentence Embeddings Multilingual using Knowledge Distillation | Reimers, Gurevych | EMNLP 2020 | `[revisado]` | https://aclanthology.org/2020.emnlp-main.365/ | R |
| 51 | Multilingual E5 Text Embeddings: A Technical Report | Wang, L., Yang, Huang, Yang, Majumder, Wei | arXiv 2402.05672, 2024 | `[preprint]` | https://arxiv.org/abs/2402.05672 | TC (HTML) |
| 52 | M3-Embedding: Multi-Linguality, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation | Chen, Xiao, Zhang, Luo, Lian, Liu | Findings of ACL 2024 | `[revisado]` | https://aclanthology.org/2024.findings-acl.137 | R |
| 53 | Qwen3 Embedding: Advancing Text Embedding and Reranking Through Foundation Models; cartão Qwen3-Embedding-0.6B | Zhang, Y. et al. | arXiv 2506.05176, 2025 | `[preprint]` + `[doc]` | https://arxiv.org/abs/2506.05176 ; https://huggingface.co/Qwen/Qwen3-Embedding-0.6B | R + D |
| 54 | EmbeddingGemma: Powerful and Lightweight Text Representations; cartão embeddinggemma-300m | Schechter Vera et al. (Google) | arXiv 2509.20354, 2025 | `[preprint]` + `[doc]` | https://arxiv.org/abs/2509.20354 ; https://huggingface.co/google/embeddinggemma-300m | TC (tabela 5) + D |
| 55 | intfloat/multilingual-e5-small (cartão do modelo) | Microsoft (intfloat) | Hugging Face | `[doc]` | https://huggingface.co/intfloat/multilingual-e5-small | D |
| 56 | MTEB: Massive Text Embedding Benchmark | Muennighoff, Tazi, Magne, Reimers | EACL 2023 | `[revisado]` | https://aclanthology.org/2023.eacl-main.148/ | R |
| 57 | MMTEB: Massive Multilingual Text Embedding Benchmark | Enevoldsen et al. | ICLR (aceito, segundo o arXiv), 2025 | `[revisado]` | https://arxiv.org/abs/2502.13595 | R |
| 58 | Beyond Multilingual Averages: MTEB-PT, a Benchmark for Portuguese Sentence Encoders | Okamura, Alcoforado, Costa | BRACIS 2026 (aceito, segundo o arXiv) | `[revisado]` | https://arxiv.org/abs/2607.04071 | TC (HTML, tabela 3) |
| 59 | MTEB-BR: A Text Embedding Benchmark for Brazilian Portuguese | Stekel | arXiv 2607.04581, 2026 | `[preprint]` | https://arxiv.org/abs/2607.04581 | TC (parcial) |
| 60 | Matryoshka Representation Learning | Kusupati et al. | NeurIPS 2022 | `[revisado]` | https://proceedings.neurips.cc/paper_files/paper/2022/hash/c32319f4868da7613d78af9993100e42-Abstract.html | R |
| 61 | Is Cosine-Similarity of Embeddings Really About Similarity? | Steck, Ekanadham, Kallus | WWW 2024 Companion | `[revisado]` | https://arxiv.org/abs/2403.05440 | R |
| 62 | pgvector (README) | pgvector | documentação | `[doc]` | https://github.com/pgvector/pgvector | D |
| 63 | pgvector 0.8.0 released | PostgreSQL News | 2024 | `[doc]` | https://www.postgresql.org/about/news/pgvector-080-released-2952/ | B |
| 64 | Manage Fin AI Agent's escalation guidance and rules | Intercom | Help Center | `[doc]` | https://www.intercom.com/help/en/articles/12396892-manage-fin-ai-agent-s-escalation-guidance-and-rules | D |
| 65 | Ask a teammate for help with Fin's replies (Human in the loop) | Intercom | Help Center | `[doc]` | https://www.intercom.com/help/en/articles/16198358-ask-a-teammate-for-help-with-fin-s-replies-human-in-the-loop | D |
| 66 | Agent Bots | Chatwoot | documentação | `[doc]` | https://www.chatwoot.com/docs/product/others/agent-bots/ | B |
| 67 | Path to high-quality LLM-based Dasher support automation | Jia, Wang, Bamba, Wang (DoorDash) | DoorDash Engineering, 2024 | `[mercado]` | https://careersatdoordash.com/?p=12568 | B (acesso bloqueado) |
| 68 | DoorDash Builds LLM Conversation Simulator to Test Customer Support Chatbots at Scale | Kumili (InfoQ), sobre post da DoorDash | InfoQ, 2026 | `[mercado]` | https://www.infoq.com/news/2026/03/doordash-llm-chatbot-simulator/ | TC (cobertura) |
| 69 | Building effective agents | Schluntz, Zhang (Anthropic) | Anthropic, 2024 | `[mercado]` | https://www.anthropic.com/research/building-effective-agents | TC |
| 70 | An empirical characterization of event sourced systems and their schema evolution: Lessons from industry | Overeem, Spoor, Jansen, Brinkkemper | Journal of Systems and Software 178, 2021 | `[revisado]` | https://doi.org/10.1016/j.jss.2021.110970 | R |
| 71 | Lost in the Middle: How Language Models Use Long Contexts | Liu, N. F., Lin, Hewitt, Paranjape, Bevilacqua, Petroni, Liang | TACL 12, 2024 | `[revisado]` | https://aclanthology.org/2024.tacl-1.9/ | R |
| 72 | On Faithfulness and Factuality in Abstractive Summarization | Maynez, Narayan, Bohnet, McDonald | ACL 2020 | `[revisado]` | https://aclanthology.org/2020.acl-main.173 | R |
| 73 | Gartner Survey Finds 64% of Customers Would Prefer That Companies Didn't Use AI for Customer Service | Gartner | comunicado, 2024-07-09 | `[mercado]` | https://www.gartner.com/en/newsroom/press-releases/2024-07-09-gartner-survey-finds-64-percent-of-customers-would-prefer-that-companies-didnt-use-ai-for-customer-service | B |
| 74 | Klarna is hiring humans again as AI replacements fail to deliver | TechSpot, sobre entrevista à Bloomberg (8/5/2025) | 2025 | `[mercado]` | https://www.techspot.com/news/107881-klarna-hiring-humans-again-ai-replacements-fail-deliver.html | B |
| 75 | BC Tribunal Confirms Companies Remain Liable for Information Provided by AI Chatbot (Moffatt v. Air Canada, 2024 BCCRT 149) | American Bar Association, Business Law Today | 2024 | `[mercado]` | https://www.americanbar.org/groups/business_law/resources/business-law-today/2024-february/bc-tribunal-confirms-companies-remain-liable-information-provided-ai-chatbot/ | B |
| 76 | Meet Gabriel: the AI Agent Running Customer Support for Millions of InfinitePay Users | CloudWalk | Newsroom, 2026-07-02 | `[mercado]` | https://www.cloudwalk.io/newsroom/meet-gabriel-the-ai-agent-running-customer-support-for-millions-of-infinitepay-users | TC |

**Antes da banca:** conferir no texto completo os números marcados como resumo (R) ou busca (B), em especial [17], [21], [35], [38], [40], [42], [44], [67] e [73].
