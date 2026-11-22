# API para o front-end

Base: `http://localhost:8000`. Referência completa e interativa (OpenAPI): `http://localhost:8000/docs`.
CORS liberado. Sem autenticação: o perfil é escolhido na tela (limitação declarada).
As telas releem a cada 2 s (sem canal ao vivo nesta entrega).

Subir tudo: `docker compose up -d --build`. Verificar: `.venv\Scripts\python testes\fumaca.py`.

## Telas sugeridas

| Tela | Perfil | Endpoints |
|---|---|---|
| Chat do cliente (simulador) | lojista | `POST /mensagens`, `GET /conversas/{id}` |
| Painel do analista | analista | `GET /painel/atendentes`, `GET /painel/fila`, `GET /painel/atendentes/{id}/conversas`, `GET /conversas/{id}`, `POST /painel/conversas/{id}/assumir`, `.../responder`, `.../devolver`, `.../encerrar` |
| Configuração de filas | supervisor | `GET /filas/ativa`, `GET /filas/versoes`, `GET /filas/grupos`, `POST /filas/validar`, `POST /filas/versoes`, `POST /filas/versoes/{n}/ativar`, `POST /filas/simular` |
| Saúde da operação | supervisor | `GET /supervisor/metricas`, `GET /supervisor/reconciliacao`, `GET /outbox/erros`, `POST /outbox/{id}/reprocessar` |

## Chat do cliente

```http
POST /mensagens
{"canal": "chat", "marca": "infinitepay", "identificador": "app-1001",
 "nome": "Loja da Ana", "conteudo": "meu repasse não caiu", "id_externo": "opcional"}
```

Resposta: `{"id_conversa": "...", "id_mensagem": "...", "duplicada": false, "estado": "na_fila"}`.
`canal`: `chat`, `whatsapp`, `email`. `marca`: `infinitepay` (português) ou `jim` (inglês).
Mesmo `identificador` e marca = mesmo cliente. Reenviar o mesmo `id_externo` devolve `duplicada: true`.
Para ver a resposta da IA, releia `GET /conversas/{id_conversa}` e mostre `mensagens` (ordem já vem certa).
"quero falar com um atendente" / "talk to a human" escala para humano.

## Conversa (detalhe)

`GET /conversas/{id}` devolve:
- `conversa`: estado (`nova`, `na_fila`, `com_ia`, `escalada`, `com_humano`, `resolvida`), marca, canal, categoria, prioridade (1 a 3), sentimento, `id_fila`, `atendente`, `cliente`.
- `mensagens`: `autor_tipo` (`cliente`, `ia`, `humano`, `sistema`), `conteudo`, `criada_em`.
- `auditoria`: toda decisão (`triagem`, `decisao_roteamento`, `decisao_distribuicao`, `transicao`, `evento_descartado`...), com `payload`.
- `escalas`: `motivo`, `resumo`, `fontes` (ids de mensagens que sustentam o resumo; destaque-as), `reserva` (true = resumo montado pela plataforma).
- `perfil`: perfil operacional do cliente (contatos e escalas em 30 dias, canal preferido, último assunto).

`GET /conversas?estado=com_ia&marca=jim&limite=50` lista.

## Painel do analista

1. Escolher o analista: `GET /painel/atendentes` (use os de `tipo = humano`).
2. Fila de escalas: `GET /painel/fila?marca=jim` (ou `?equipe=support-us`), com espera em segundos e o resumo da escala.
3. Minhas conversas: `GET /painel/atendentes/{id}/conversas`.
4. Ações (corpo sempre com `id_atendente`):

```http
POST /painel/conversas/{id}/assumir    {"id_atendente": "..."}
POST /painel/conversas/{id}/responder  {"id_atendente": "...", "conteudo": "texto"}
POST /painel/conversas/{id}/devolver   {"id_atendente": "...", "nota": "orientação para a IA"}
POST /painel/conversas/{id}/encerrar   {"id_atendente": "..."}
```

`409` = a conversa não está com esse analista ou ele está sem capacidade (3 conversas); mostre a mensagem.
O distribuidor também entrega escalas sozinho a analistas livres; a conversa aparece em "minhas conversas".

## Configuração de filas

`GET /filas/ativa` devolve `{"numero": 1, "filas": {"fila_padrao": "padrao", "filas": [...]}}`. Cada fila:

```json
{"id": "jim-geral", "nome": "JIM - General", "ordem": 6, "prioridade": 1, "ativa": true,
 "ao_abrir_disjuntor": "reter",
 "condicoes": {"todas": [{"campo": "marca", "operador": "igual", "valor": "jim"}]},
 "atendentes": [{"tipo": "ia", "id": "ia-jim"}, {"tipo": "equipe", "id": "support-us"}]}
```

Campos: `marca`, `canal`, `categoria`, `prioridade`, `idioma`, `segmento_cliente`, `sentimento`, `origem`.
Operadores: `igual`, `diferente`, `em` (valor é lista). Combinação: `todas` ou `qualquer`.
Grupos válidos: `GET /filas/grupos`. Fluxo da tela: editar → `POST /filas/validar` (mostra `erros`) →
`POST /filas/versoes {"regras": {...}, "criada_por": "nome"}` → `POST /filas/versoes/{n}/ativar`.
Rollback = ativar uma versão anterior. Simular: `POST /filas/simular {"atendimento": {"marca": "jim", "categoria": "repasse", "origem": "cliente"}}`.

## Saúde da operação

`GET /supervisor/metricas`: conversas por estado, tamanho e espera máxima por fila, escalas da última hora por motivo, outbox por status, ocupação dos atendentes, descartes por fencing, chaves de ablação em uso.
`GET /supervisor/reconciliacao`: invariantes I1 a I6 com total e exemplos (o esperado é zero).

## Para a demonstração

| Ação | Comando |
|---|---|
| Agente lento (escala por timeout) | `POST http://localhost:8200/modo {"modo": "lento"}` |
| Agente fora | `{"modo": "fora"}`; voltar com `{"modo": "normal"}` |
| Agente duplicando respostas | `{"modo": "duplicar"}` |
| Broker fora | `docker compose stop broker` / `start broker` |
| Canal de saída fora | `POST http://localhost:8310/modo {"modo": "fora"}` |
