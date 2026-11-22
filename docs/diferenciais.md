# Diferenciais

Ideias além do que o TAPI exige. Nenhuma entra na entrega de 23/11 (decisão D-2, 2026-11-20, e plano de 2 dias, arquitetura 19.1). O D6 foi aprovado pelo usuário e fica como Evolução, inclusive a versão reduzida.

| # | Diferencial | Esforço | Reaproveita do núcleo |
|---|---|---|---|
| D1 | Persona da IA por marca | Pequeno | Cadastro de marcas, `conversa.atribuida` |
| D2 | Fila de qualidade | Pequeno/médio | Motor de filas, auditoria |
| D3 | Simulador de regras de fila | Médio | Roteador puro, registros de decisão |
| D4 | Painel ao vivo do supervisor | Médio | Log de eventos |
| D5 | Copiloto do analista | Médio | Contrato com o agente, painel do analista |
| D6 | Memória semântica | Médio | `transicionar`, contrato versionado, Postgres |

---

## D1. Persona da IA por marca

**O que é:** cada marca tem a sua forma de falar (InfinitePay em português, tom próximo; JIM em inglês, outro tom). A plataforma guarda a configuração e a entrega ao agente.

**Como funciona:** o supervisor cadastra idioma, tom, nome do atendente, mensagem de handoff e limites de ação; `conversa.atribuida` leva a persona em `dados.persona`; o mock a usa; a auditoria registra a versão da persona em cada conversa.

**Muda na arquitetura:** tabela `personas` ligada a `marcas`, versionada.

**Como medir:** teste que cada marca recebe a persona certa; trocar a persona e ver o efeito.

## D2. Fila de qualidade

**O que é:** amostra das conversas resolvidas pela IA vai para revisão humana. Responde ao τ-bench: o agente acerta muitas vezes, mas não sempre.

**Como funciona:** ao resolver, a plataforma sorteia (taxa por marca e categoria, ex.: 5% no geral, 20% em crédito; valores de exemplo); a sorteada entra numa fila comum com `origem = amostra_qualidade`; o revisor usa uma rubrica curta; o resultado vira taxa de erro por categoria, que orienta mudar a regra.

**Muda na arquitetura:** um valor novo em `origem` e uma tabela de avaliações.

**Como medir:** taxa de erro por categoria; regras ajustadas a partir das revisões.

## D3. Simulador de regras de fila

**O que é:** antes de ativar regras novas, o supervisor testa o impacto com atendimentos passados.

**Como funciona:** as entradas dos registros de decisão de roteamento (arquitetura 12.1) passam pelo roteador com as regras novas; sai quantos mudariam de fila e quais filas ficariam vazias ou lotadas.

**Muda na arquitetura:** nada, se o roteador for função pura. Serve também ao experimento sugerido no TAPI ("avaliação da distribuição de filas").

**Como medir:** distribuição prevista contra a real depois de ativar.

## D4. Painel ao vivo do supervisor

**O que é:** a saúde da operação em tempo real: tamanho e espera por fila, SLA em risco, escalonamento, analistas disponíveis, estado do disjuntor.

**Como funciona:** um consumidor que só lê e agrega os eventos de auditoria; a tela atualiza sozinha (na entrega, leitura a cada 2 s; SSE é evolução); alertas por limite (valores de exemplo).

**Por que vale:** dá dono ao supervisor e mostra o teste de carga ao vivo na demonstração.

**Como medir:** no pico, tempo até o painel mostrar que uma fila estourou.

## D5. Copiloto do analista

**O que é:** com a conversa num humano, a IA sugere a resposta e o analista aceita, edita ou descarta.

**Como funciona:** eventos novos `sugestao.solicitada` e `sugestao.gerada`, opcionais dentro da versão 1.x do contrato; rascunho no painel; a escolha é registrada.

**Por que vale:** na versão publicada de Brynjolfsson et al. (QJE 2025), +15% de conversas resolvidas por hora; os menos experientes ganharam velocidade e qualidade, e os mais experientes tiveram pequena queda de qualidade. Os +14% e +34% são do working paper (NBER, 2023).

**Como medir:** sugestões aceitas sem edição, editadas e descartadas, por experiência do analista.

## D6. Memória semântica (Evolução)

**O que é:** um transformer pré-treinado gera o embedding de cada mensagem do cliente e do resumo de cada conversa encerrada; a busca por cosseno recupera contexto relevante. Não resume e não treina rede neural ("usamos um transformer pré-treinado para gerar embeddings e fazer busca semântica").

**Partes**
1. **Trechos relevantes na atribuição:** top-k do histórico do próprio cliente, na mesma marca, acima de uma similaridade mínima, somados ao perfil e às últimas N (que já estão na entrega). Base: Park et al. (2023), relevância = cosseno entre embeddings; Lewis et al. (2020), recuperação num índice vetorial denso; Reimers e Gurevych (2019), embeddings de frase comparáveis por cosseno.
2. **Casos parecidos no painel:** até 3 conversas encerradas de outros clientes da marca, só com categoria, resumo mascarado, ações e desfecho. Por analogia com o COTA (Molino et al., 2018), que classifica e seleciona respostas.
3. **Detector de incidente:** agrupa mensagens recentes por similaridade e conta clientes distintos por categoria; cruza com fila de erros, timeouts e falhas de integração, porque o mesmo incidente chega com palavras diferentes (Liu et al., ICSE 2023, iPACK). Agrupamento: Petrović et al. (2010).

**Muda na arquitetura:** pgvector no mesmo Postgres (imagem com versão fixa, ex.: `pgvector/pgvector:0.8.7-pg16`); pendência de vetor gravada por `transicionar` na mesma transação, fora da outbox; worker em lote; serviço de embeddings fora do núcleo; vetor da consulta calculado fora da transação, com prazo curto. Plano B: serviço fora → a conversa segue com perfil e últimas N.

**Modelo (escolha por teste)**

| Opção | A favor | Contra |
|---|---|---|
| Qwen3-Embedding-0.6B | 78,9 em recuperação no MTEB-PT; Apache 2.0; dimensão de 32 a 1024 | Mais pesado em CPU; instrução na consulta |
| multilingual-e5-small | 384 dimensões; MIT; 70,2 em recuperação | Prefixos obrigatórios; 512 tokens |
| mmBERT base | Encoder recente, 1.800+ línguas | Sem ajuste, 17,6 em recuperação; ajustar é treinar |

Números do MTEB-PT (Okamura et al., preprint aceito no BRACIS 2026, tabela 3). Versão reduzida: só e5-small contra recência, sem casos parecidos e sem detector; critério inclui a vazão do worker contra a taxa de entrada.

**Riscos:** embedding é dado pessoal e o texto pode ser em boa parte reconstruído (Morris et al., 2023): mesma retenção e eliminação da mensagem. Filtro por marca depois do índice HNSW devolve menos linhas: busca exata quando o filtro é seletivo, índice parcial por marca ou `hnsw.iterative_scan` (pgvector 0.8.0+). Custo: 4 × dimensões + 8 bytes por vetor. Deriva: `modelo` em cada vetor.

**Como medir:** ~100 consultas rotuladas à mão; precisão@5 e acerto@5 contra recência (Manning et al., 2008); latência adicionada; incidente injetado, inclusive parafraseado. Dados sintéticos superestimam a precisão.

---

## Decisões do núcleo que deixam os diferenciais baratos

1. **Todo evento é registrado num log.** Alimenta D2, D3 e D4.
2. **O roteador é uma função pura.** Habilita D3.
3. **O contrato aceita campos e tipos novos opcionais dentro da 1.x.** Permite D1, D5 e D6 sem quebrar.
4. **Toda mensagem passa por `transicionar`.** A pendência de vetor do D6 entraria na mesma transação.
