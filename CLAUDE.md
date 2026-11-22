# Help Desk AI First (CloudWalk / Inteli)

Projeto individual do Inteli com a CloudWalk (InfinitePay no Brasil, JIM nos EUA). **Entrega: 2026-11-23.**
Help desk próprio, AI first, multi-marca e multi-equipe, com o agente de IA (mock) como atendente dentro de filas configuráveis, integrado por webhook + broker + Kafka.

Este arquivo só aponta para os documentos e guarda as regras de trabalho. Não repita aqui o que está neles.

## Onde está cada coisa

| Documento | Para que serve |
|---|---|
| `docs/arquitetura.md` | **Fonte da verdade:** requisitos, decisões (tabela da seção 20), plano de fatias (seção 19), plano de corte |
| `docs/implementacao.md` | Como construir: SQL, contrato campo a campo, algoritmos, configuração, testes e pronto por fatia |
| `docs/referencias.md` | Base científica e de mercado, com o nível de conferência de cada fonte |
| `docs/diferenciais.md` | Diferenciais e o que ficou para Evolução (D6, memória semântica) |
| `docs/diario.md` | Registro de cada parte construída. **A última entrada diz onde paramos** |
| `docs/revisoes/` | Revisões da arquitetura (validador e auditoria por rodada) |
| `docs/pesquisa_diferenciais.md` | Pesquisa de diferenciais, ainda não aprovada; só entra na arquitetura depois de debate |

Se este arquivo e a arquitetura divergirem, vale a arquitetura.

## Como trabalhar comigo

- Responda sempre em **português**.
- **Passo a passo.** Uma fatia por vez, e dentro dela uma parte por vez. Não adiante etapas.
- **Explique antes de fazer.** Preciso entender e defender cada decisão numa banca.
- **Você propõe, eu valido.** Decisão nova vem com recomendação e justificativa curta; espere meu ok. Status de decisão (Proposta, Decidida) só muda com o meu aval.
- **Estresse as ideias.** Se algo tiver furo de arquitetura, aponte.
- **Evidência:** número só com fonte; sem fonte, é hipótese. Cite só fonte conferida e diga se viu o texto completo ou o resumo.
- Documentação e comentários **enxutos e sem cara de IA**: sem enfeite, sem emoji.

## Divisão do trabalho (desde 2026-11-21)

Com a entrega em 23/11, o Claude implementa o backend inteiro (banco, API, broker, mock, agendador, filas, experimento) sem o modo misto e sem esperar ok por parte; eu faço o front-end consumindo a API. O ritual abaixo vale para o front-end e para decisões de arquitetura. Commits continuam pequenos e descritos no diário.

## Ritual de cada parte

1. **Ficha (antes).** Objetivo em uma frase; conceito e onde aparece na arquitetura; arquivos criados ou alterados; o que eu vou escrever; como saber que funcionou. Esperar meu ok.
2. **Execução.** Só aquela parte. **Modo misto:** você escreve a estrutura e o encanamento; o trecho central (a regra que a banca vai perguntar) fica para mim, com um teste que falha até eu implementar. Depois revise o que escrevi.
3. **Verificação.** Comandos um por vez, com o que observar. Duas ou três perguntas de banca.
4. **Registro.** Depois da minha confirmação: entrada em `docs/diario.md` e commit. Nada de commit antes de eu ver.

## Regras do repositório

- Nomes de eventos, campos, tabelas e módulos em português.
- Commits pequenos, em português, no formato `feat: ...`, `fix: ...`, `docs: ...`.
- Ambiente local: Postgres na porta 5433 e Kafka na 19092 (não colidir com outros projetos). Testes Python com `.venv\Scripts\python -m pytest`.
- Nunca versionar `.env`, dados reais ou chaves. Só dados sintéticos (LGPD).
