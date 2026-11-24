"use client";

import Link from "next/link";
import { useState } from "react";
import {
  CabecalhoConversa,
  Historico,
  LinhaDoTempo,
  ListaEscalas,
  PerfilCliente,
} from "@/components/conversa";
import { Atualizado, Aviso, Botao, Cartao, campo, Etiqueta, EtiquetaEstado, Rotulo, Vazio } from "@/components/ui";
import { apiPost, textoDoErro } from "@/lib/api";
import { duracao, hora } from "@/lib/formatar";
import type { Atendente, ConversaDoAtendente, DetalheConversa, ItemFila } from "@/lib/tipos";
import { useSondagem } from "@/lib/useSondagem";

type Escopo = "equipe" | "marca" | "tudo";

export default function PainelAnalista() {
  const [idEscolhido, setIdEscolhido] = useState<string | null>(null);
  const [escopo, setEscopo] = useState<Escopo>("equipe");
  const [selecionada, setSelecionada] = useState<string | null>(null);
  const [resposta, setResposta] = useState("");
  const [nota, setNota] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "erro" | "ok"; texto: string } | null>(null);

  const atendentes = useSondagem<Atendente[]>("/painel/atendentes", 2000);
  const humanos = (atendentes.dados ?? []).filter((a) => a.tipo === "humano");
  const analista = humanos.find((a) => a.id === idEscolhido) ?? humanos[0] ?? null;
  const nomes = Object.fromEntries((atendentes.dados ?? []).map((a) => [a.id, a.nome]));

  const caminhoFila = !analista
    ? null
    : escopo === "equipe"
      ? `/painel/fila?equipe=${encodeURIComponent(analista.id_equipe)}`
      : escopo === "marca"
        ? `/painel/fila?marca=${analista.marca}`
        : "/painel/fila";
  const fila = useSondagem<ItemFila[]>(caminhoFila);
  const minhas = useSondagem<ConversaDoAtendente[]>(analista ? `/painel/atendentes/${analista.id}/conversas` : null);
  const detalhe = useSondagem<DetalheConversa>(selecionada ? `/conversas/${selecionada}` : null);

  const c = detalhe.dados?.conversa;
  const ehMinha = !!(c && analista && c.estado === "com_humano" && c.id_atendente === analista.id);
  const podeAssumir = !!(c && (c.estado === "escalada" || c.estado === "na_fila"));
  const ultimaEscala = detalhe.dados?.escalas.at(-1);

  async function acao(rota: string, corpo: Record<string, unknown>, ok: string, depois?: () => void) {
    if (!analista) return;
    setOcupado(true);
    setAviso(null);
    try {
      await apiPost(rota, { id_atendente: analista.id, ...corpo });
      setAviso({ tipo: "ok", texto: ok });
      depois?.();
    } catch (e) {
      setAviso({ tipo: "erro", texto: textoDoErro(e) });
    } finally {
      setOcupado(false);
      fila.recarregar();
      minhas.recarregar();
      detalhe.recarregar();
      atendentes.recarregar();
    }
  }

  function selecionar(id: string) {
    setSelecionada(id);
    setAviso(null);
    setResposta("");
    setNota("");
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-4">
        <Rotulo texto="Analista">
          <select
            className={campo}
            value={analista?.id ?? ""}
            onChange={(e) => {
              setIdEscolhido(e.target.value);
              setSelecionada(null);
              setAviso(null);
            }}
          >
            {humanos.map((a) => (
              <option key={a.id} value={a.id}>
                {a.nome} · {a.id_equipe} ({a.marca})
              </option>
            ))}
          </select>
        </Rotulo>
        {analista && (
          <div className="text-sm text-zinc-600">
            Ocupação <strong>{analista.ativas}/{analista.capacidade}</strong> · {analista.status}
          </div>
        )}
        <Rotulo texto="Fila mostrada">
          <select className={campo} value={escopo} onChange={(e) => setEscopo(e.target.value as Escopo)}>
            <option value="equipe">Filas da minha equipe</option>
            <option value="marca">Toda a marca</option>
            <option value="tudo">Todas</option>
          </select>
        </Rotulo>
        <Atualizado em={atendentes.atualizadoEm} erro={atendentes.erro} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
        <div className="flex flex-col gap-4">
          <Cartao titulo={`Minhas conversas (${minhas.dados?.length ?? 0})`} acoes={<Atualizado em={minhas.atualizadoEm} erro={minhas.erro} />}>
            {minhas.dados?.length ? (
              <ul className="flex flex-col gap-1">
                {minhas.dados.map((m) => (
                  <li key={m.id}>
                    <button
                      type="button"
                      onClick={() => selecionar(m.id)}
                      className={`w-full rounded px-2 py-1.5 text-left text-sm hover:bg-zinc-50 ${selecionada === m.id ? "bg-zinc-100" : ""}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{m.cliente}</span>
                        <EtiquetaEstado estado={m.estado} />
                      </div>
                      <div className="text-xs text-zinc-500">
                        {m.marca} · {m.canal} · {m.categoria} · p{m.prioridade} · {hora(m.atualizada_em)}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <Vazio>{minhas.dados ? "Nenhuma conversa com você. O distribuidor também entrega escalas sozinho." : "Carregando…"}</Vazio>
            )}
          </Cartao>

          <Cartao titulo={`Fila: escaladas e aguardando (${fila.dados?.length ?? 0})`} acoes={<Atualizado em={fila.atualizadoEm} erro={fila.erro} />}>
            {fila.dados?.length ? (
              <ul className="flex max-h-[60vh] flex-col gap-1 overflow-y-auto">
                {fila.dados.map((f) => (
                  <li key={f.id} className={`rounded border border-zinc-100 ${selecionada === f.id ? "bg-zinc-100" : ""}`}>
                    <button type="button" onClick={() => selecionar(f.id)} className="w-full px-2 py-1.5 text-left text-sm hover:bg-zinc-50">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{f.cliente}</span>
                        <span className="text-xs text-zinc-500">espera {duracao(f.espera_s)}</span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 text-xs text-zinc-500">
                        <EtiquetaEstado estado={f.estado} />
                        <span>{f.id_fila}</span>
                        <span>p{f.prioridade}</span>
                        <span>{f.categoria}</span>
                        {f.motivo && <Etiqueta cor="bg-red-50 text-red-700">{f.motivo}</Etiqueta>}
                      </div>
                      {f.resumo && <p className="mt-1 line-clamp-2 text-xs text-zinc-600">{f.resumo}</p>}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <Vazio>{fila.dados ? "Fila vazia." : "Carregando…"}</Vazio>
            )}
          </Cartao>
        </div>

        <div className="flex flex-col gap-4">
          {!selecionada && (
            <Cartao>
              <Vazio>Escolha uma conversa da fila ou das suas conversas.</Vazio>
            </Cartao>
          )}
          {selecionada && !c && (
            <Cartao>
              <Atualizado em={detalhe.atualizadoEm} erro={detalhe.erro} />
            </Cartao>
          )}
          {c && detalhe.dados && (
            <>
              <Cartao
                titulo={`Conversa com ${c.cliente}`}
                acoes={
                  <>
                    <Atualizado em={detalhe.atualizadoEm} erro={detalhe.erro} />
                    <Link href={`/conversas/${c.id}`} className="text-xs text-sky-700 hover:underline">
                      tela da conversa
                    </Link>
                  </>
                }
              >
                <div className="flex flex-col gap-4">
                  <CabecalhoConversa c={c} />
                  {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}
                  <div className="flex flex-wrap gap-2">
                    <Botao
                      disabled={ocupado || !podeAssumir}
                      onClick={() => acao(`/painel/conversas/${c.id}/assumir`, {}, "Conversa assumida.")}
                    >
                      Assumir
                    </Botao>
                    <Botao
                      variante="perigo"
                      disabled={ocupado || !ehMinha}
                      onClick={() => acao(`/painel/conversas/${c.id}/encerrar`, {}, "Conversa encerrada.")}
                    >
                      Encerrar
                    </Botao>
                    {!ehMinha && !podeAssumir && (
                      <span className="self-center text-xs text-zinc-500">
                        Responder, devolver e encerrar só com a conversa com você (estado com analista).
                      </span>
                    )}
                  </div>
                </div>
              </Cartao>

              {ultimaEscala && (
                <Cartao titulo="Resumo da escala">
                  <ListaEscalas escalas={[ultimaEscala]} />
                  <p className="mt-2 text-xs text-zinc-500">As mensagens que sustentam o resumo estão destacadas no histórico.</p>
                </Cartao>
              )}

              <div className="grid gap-4 xl:grid-cols-[1fr_300px]">
                <Cartao titulo="Histórico">
                  <div className="flex flex-col">
                    <Historico mensagens={detalhe.dados.mensagens} fontes={ultimaEscala?.fontes ?? []} nomes={nomes} />
                  </div>
                  <div className="mt-4 flex flex-col gap-2 border-t border-zinc-100 pt-4">
                    <textarea
                      className={campo}
                      rows={3}
                      placeholder="Resposta ao cliente"
                      value={resposta}
                      onChange={(e) => setResposta(e.target.value)}
                      disabled={!ehMinha}
                    />
                    <div>
                      <Botao
                        disabled={ocupado || !ehMinha || !resposta.trim()}
                        onClick={() =>
                          acao(`/painel/conversas/${c.id}/responder`, { conteudo: resposta.trim() }, "Resposta enviada.", () =>
                            setResposta(""),
                          )
                        }
                      >
                        Responder
                      </Botao>
                    </div>
                    <textarea
                      className={campo}
                      rows={2}
                      placeholder="Nota para a IA ao devolver (opcional)"
                      value={nota}
                      onChange={(e) => setNota(e.target.value)}
                      disabled={!ehMinha}
                    />
                    <div>
                      <Botao
                        variante="secundario"
                        disabled={ocupado || !ehMinha}
                        onClick={() =>
                          acao(`/painel/conversas/${c.id}/devolver`, { nota }, "Conversa devolvida para a IA.", () => setNota(""))
                        }
                      >
                        Devolver para a IA
                      </Botao>
                    </div>
                  </div>
                </Cartao>
                <div className="flex flex-col gap-4">
                  <Cartao titulo="Perfil do cliente">
                    <PerfilCliente perfil={detalhe.dados.perfil} />
                  </Cartao>
                  {detalhe.dados.escalas.length > 1 && (
                    <Cartao titulo="Escalas anteriores">
                      <ListaEscalas escalas={detalhe.dados.escalas.slice(0, -1)} />
                    </Cartao>
                  )}
                </div>
              </div>

              <Cartao titulo={`Auditoria (${detalhe.dados.auditoria.length} eventos)`}>
                <LinhaDoTempo auditoria={detalhe.dados.auditoria} nomes={nomes} />
              </Cartao>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
