"use client";

import Link from "next/link";
import { useState } from "react";
import { Historico } from "@/components/conversa";
import { Atualizado, Aviso, Botao, Cartao, campo, EtiquetaEstado, Rotulo } from "@/components/ui";
import { apiPost, textoDoErro } from "@/lib/api";
import { CANAIS, MARCAS } from "@/lib/formatar";
import type { Canal, DetalheConversa, Marca, MensagemAceita } from "@/lib/tipos";
import { useSondagem } from "@/lib/useSondagem";

const IDENTIFICADOR_PADRAO: Record<Canal, string> = {
  chat: "app-1001",
  whatsapp: "+5511999990001",
  email: "loja1001@exemplo.com",
};

const SUGESTOES: Record<Marca, string[]> = {
  infinitepay: [
    "meu repasse não caiu",
    "quero saber meu saldo",
    "acho que caí num golpe, não reconheço uma venda",
    "quero falar com um atendente",
  ],
  jim: ["my payout did not arrive", "my card reader is not working", "I want to talk to a human agent"],
};

interface UltimoEnvio {
  conteudo: string;
  id_externo: string;
  resposta: MensagemAceita | null;
  reenvio: boolean;
}

export default function ChatCliente() {
  const [marca, setMarca] = useState<Marca>("infinitepay");
  const [canal, setCanal] = useState<Canal>("chat");
  const [identificador, setIdentificador] = useState(IDENTIFICADOR_PADRAO.chat);
  const [nome, setNome] = useState("Loja da Ana");
  const [texto, setTexto] = useState("");
  const [idConversa, setIdConversa] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [ultimo, setUltimo] = useState<UltimoEnvio | null>(null);

  const { dados, erro: erroLeitura, atualizadoEm } = useSondagem<DetalheConversa>(
    idConversa ? `/conversas/${idConversa}` : null,
  );

  function trocarCliente(mudanca: () => void) {
    mudanca();
    setIdConversa(null);
    setUltimo(null);
    setErro(null);
  }

  async function enviar(conteudo: string, idExterno: string, reenvio: boolean) {
    setEnviando(true);
    setErro(null);
    try {
      const r = await apiPost<MensagemAceita>("/mensagens", {
        canal,
        marca,
        identificador,
        nome: nome || undefined,
        conteudo,
        id_externo: idExterno,
      });
      if (r.id_conversa) setIdConversa(r.id_conversa);
      setUltimo({ conteudo, id_externo: idExterno, resposta: r, reenvio });
      if (!reenvio) setTexto("");
    } catch (e) {
      setErro(textoDoErro(e));
    } finally {
      setEnviando(false);
    }
  }

  const c = dados?.conversa;

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <div className="flex flex-col gap-4">
        <Cartao titulo="Lojista simulado">
          <div className="flex flex-col gap-3">
            <Rotulo texto="Marca">
              <select className={campo} value={marca} onChange={(e) => trocarCliente(() => setMarca(e.target.value as Marca))}>
                {MARCAS.map((m) => (
                  <option key={m} value={m}>
                    {m === "infinitepay" ? "InfinitePay (português)" : "JIM (inglês)"}
                  </option>
                ))}
              </select>
            </Rotulo>
            <Rotulo texto="Canal">
              <select
                className={campo}
                value={canal}
                onChange={(e) =>
                  trocarCliente(() => {
                    const novo = e.target.value as Canal;
                    setCanal(novo);
                    setIdentificador(IDENTIFICADOR_PADRAO[novo]);
                  })
                }
              >
                {CANAIS.map((x) => (
                  <option key={x} value={x}>{x}</option>
                ))}
              </select>
            </Rotulo>
            <Rotulo texto="Identificador (id do app, telefone ou e-mail)">
              <div className="flex gap-2">
                <input
                  className={`${campo} flex-1`}
                  value={identificador}
                  onChange={(e) => trocarCliente(() => setIdentificador(e.target.value))}
                />
                <Botao
                  variante="secundario"
                  title="Gera um identificador novo (cliente novo)"
                  onClick={() =>
                    trocarCliente(() =>
                      setIdentificador(IDENTIFICADOR_PADRAO[canal].replace("1001", String(Math.floor(Math.random() * 9000) + 1000))),
                    )
                  }
                >
                  Novo
                </Botao>
              </div>
            </Rotulo>
            <Rotulo texto="Nome (só no primeiro contato)">
              <input className={campo} value={nome} onChange={(e) => setNome(e.target.value)} />
            </Rotulo>
            <p className="text-xs text-zinc-500">
              Mesmo identificador, canal e marca = mesmo cliente. Uma conversa aberta por cliente e marca; depois de
              resolvida, a próxima mensagem abre outra.
            </p>
          </div>
        </Cartao>

        {ultimo && (
          <Cartao titulo="Último envio">
            <div className="flex flex-col gap-2 text-sm">
              <p className="text-zinc-700">&ldquo;{ultimo.conteudo}&rdquo;</p>
              <p className="text-xs text-zinc-500">
                id_externo <code>{ultimo.id_externo}</code>
              </p>
              {ultimo.resposta && (
                <Aviso tipo={ultimo.resposta.duplicada ? "info" : "ok"}>
                  {ultimo.reenvio ? "Reenvio: " : ""}duplicada = {String(ultimo.resposta.duplicada)}
                  {ultimo.resposta.estado ? ` · estado ${ultimo.resposta.estado}` : ""}
                  {ultimo.resposta.duplicada && " (a inbox da entrada descartou; nenhuma mensagem nova)"}
                </Aviso>
              )}
              <Botao
                variante="secundario"
                disabled={enviando}
                onClick={() => enviar(ultimo.conteudo, ultimo.id_externo, true)}
                title="Simula o canal reenviando a mesma mensagem"
              >
                Reenviar com o mesmo id_externo
              </Botao>
            </div>
          </Cartao>
        )}
      </div>

      <Cartao
        titulo={
          <span className="flex items-center gap-2">
            Conversa {c && <EtiquetaEstado estado={c.estado} />}
          </span>
        }
        acoes={
          idConversa && (
            <>
              <Atualizado em={atualizadoEm} erro={erroLeitura} />
              <Link href={`/conversas/${idConversa}`} className="text-xs text-sky-700 hover:underline">
                ver auditoria
              </Link>
            </>
          )
        }
      >
        <div className="flex min-h-[420px] flex-col gap-4">
          {c && (
            <p className="text-xs text-zinc-500">
              {c.cliente} · fila {c.id_fila ?? "—"} · atendente {c.atendente ?? "—"} · categoria {c.categoria} ·
              prioridade {c.prioridade}
            </p>
          )}
          <div className="flex-1">
            {dados ? (
              <div className="flex flex-col">
                <Historico mensagens={dados.mensagens} />
              </div>
            ) : (
              <p className="text-sm text-zinc-400">
                {idConversa ? "Carregando a conversa…" : "Escreva a primeira mensagem para abrir uma conversa."}
              </p>
            )}
          </div>

          {erro && <Aviso>{erro}</Aviso>}

          <div className="flex flex-wrap gap-1.5">
            {SUGESTOES[marca].map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setTexto(s)}
                className="rounded-full border border-zinc-200 px-2.5 py-1 text-xs text-zinc-600 hover:bg-zinc-50"
              >
                {s}
              </button>
            ))}
          </div>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (texto.trim()) void enviar(texto.trim(), crypto.randomUUID(), false);
            }}
          >
            <input
              className={`${campo} flex-1`}
              placeholder={marca === "jim" ? "Type a message" : "Escreva uma mensagem"}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
            />
            <Botao type="submit" disabled={enviando || !texto.trim() || !identificador.trim()}>
              {enviando ? "Enviando…" : "Enviar"}
            </Botao>
          </form>
        </div>
      </Cartao>
    </div>
  );
}
