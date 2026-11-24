# Front-end

Next.js 16 (App Router), TypeScript e Tailwind. Consome a API do núcleo pelo navegador; o contrato está em
`../docs/api-front.md`. Sem autenticação: o perfil (cliente, analista, supervisor) é escolhido na tela.

## Rodar

Requisitos: Node 24 e a API no ar (`docker compose up -d` na raiz).

```bash
cd front
npm install
npm run dev          # http://localhost:3000
```

A API é lida de `NEXT_PUBLIC_API_URL` (padrão `http://localhost:8000`). Para outra URL, crie `front/.env.local`
com `NEXT_PUBLIC_API_URL=http://host:porta`.

Verificação: `npm run build`, `npx tsc --noEmit` e `npm run lint`.

## Telas e itens do TAP

| Tela | Perfil | Item do TAP | Rotas da API |
|---|---|---|---|
| `/cliente` | lojista | 1. Conversa entre cliente e atendente | `POST /mensagens`, `GET /conversas/{id}` |
| `/analista` | analista | 2. Painel do analista humano | `/painel/atendentes`, `/painel/fila`, `/painel/atendentes/{id}/conversas`, `/conversas/{id}`, `/painel/conversas/{id}/assumir`, `responder`, `devolver`, `encerrar` |
| `/filas` | supervisor | 3. Filas configuráveis sem deploy | `/filas/ativa`, `/filas/versoes`, `/filas/grupos`, `/filas/validar`, `/filas/simular`, `POST /filas/versoes`, `/filas/versoes/{n}/ativar` |
| `/conversas` e `/conversas/{id}` | supervisor | 4. Rastreabilidade: linha do tempo da auditoria com o porquê de cada decisão | `GET /conversas`, `GET /conversas/{id}` |
| `/supervisor` | supervisor | 4. Saúde da operação | `/supervisor/metricas`, `/outbox/erros`, `POST /outbox/{id}/reprocessar`, `/supervisor/reconciliacao` |

- Chat: escolhe marca e canal, envia, relê a conversa a cada 2 s. "Reenviar com o mesmo id_externo" mostra a
  deduplicação da entrada (`duplicada = true`).
- Painel: resumo da última escala com as mensagens-fonte destacadas no histórico, perfil e auditoria. O `409`
  da API (conversa não está com o analista, ou analista sem capacidade) aparece na tela.
- Filas: editor por formulário ou JSON, a partir de qualquer versão. Rollback é ativar uma versão anterior.
- Supervisor: relê a cada 5 s por padrão (ajustável). A reconciliação só roda no botão, porque varre as tabelas.

## Releitura

`src/lib/useSondagem.ts`: a próxima leitura só é agendada quando a anterior termina, então não há requisições
acumuladas em paralelo; trocar de tela ou de conversa cancela a leitura em curso. Em `npm run dev` o React
monta cada efeito duas vezes, e a primeira leitura aparece como cancelada na aba de rede.
