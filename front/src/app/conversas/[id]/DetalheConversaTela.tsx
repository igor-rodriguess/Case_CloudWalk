"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { apiGet, textoDoErro } from "@/lib/api";
import {
  CabecalhoConversa,
  Historico,
  LinhaDoTempo,
  ListaEscalas,
  PerfilCliente,
  useNomesAtendentes,
} from "@/components/conversa";
import { Atualizado, Aviso, Cartao } from "@/components/ui";
import type { Conversa, DetalheConversa, Mensagem, Traco } from "@/lib/tipos";
import { useSondagem } from "@/lib/useSondagem";

export function DetalheConversaTela() {
  const { id } = useParams<{ id: string }>();
  const [aoVivo, setAoVivo] = useState(true);
  const { dados, erro, atualizadoEm } = useSondagem<DetalheConversa>(`/conversas/${id}`, aoVivo ? 2000 : 0);
  const nomes = useNomesAtendentes();

  const fontes = (dados?.escalas ?? []).flatMap((e) => e.fontes ?? []);
  const descartes = (dados?.auditoria ?? []).filter((e) => e.tipo === "evento_descartado").length;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/conversas" className="text-xs text-sky-700 hover:underline">
            conversas
          </Link>
          <h1 className="text-lg font-semibold">
            Conversa <code className="text-sm font-normal">{id}</code>
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-sm text-zinc-600">
            <input type="checkbox" checked={aoVivo} onChange={(e) => setAoVivo(e.target.checked)} />
            reler a cada 2 s
          </label>
          <Atualizado em={atualizadoEm} erro={erro} />
        </div>
      </div>

      {!dados && erro && <Aviso>{erro}</Aviso>}

      {dados && (
        <>
          <Cartao titulo={dados.conversa.cliente}>
            <CabecalhoConversa c={dados.conversa} />
            <RelogioSla c={dados.conversa} agora={atualizadoEm} />
          </Cartao>

          <TraceMensagem idConversa={id} mensagens={dados.mensagens} />

          <div className="grid gap-4 lg:grid-cols-2">
            <Cartao
              titulo={`Auditoria: linha do tempo (${dados.auditoria.length} eventos)`}
              acoes={descartes > 0 && <span className="text-xs text-red-700">{descartes} descarte(s) por fencing</span>}
            >
              <p className="mb-3 text-xs text-zinc-500">
                Toda decisão da plataforma, na ordem em que foi gravada, com o porquê. Pontos vermelhos: escala, descarte
                ou rejeição.
              </p>
              <LinhaDoTempo auditoria={dados.auditoria} nomes={nomes} />
            </Cartao>

            <div className="flex flex-col gap-4">
              <Cartao titulo="Mensagens">
                <div className="flex flex-col">
                  <Historico mensagens={dados.mensagens} fontes={fontes} nomes={nomes} />
                </div>
              </Cartao>
              <Cartao titulo={`Escalas (${dados.escalas.length})`}>
                <ListaEscalas escalas={dados.escalas} />
              </Cartao>
              <Cartao titulo="Perfil operacional do cliente">
                <PerfilCliente perfil={dados.perfil} />
              </Cartao>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/** SLA da conversa: corre enquanto a operação deve resposta, pausa quando o atendente responde. */
function RelogioSla({ c, agora }: { c: Conversa; agora: Date | number | null }) {
  if (c.sla_acumulado_ms === undefined) return null;
  const correndo = Boolean(c.sla_desde);
  const ms = (c.sla_acumulado_ms ?? 0) + (correndo && c.sla_desde && agora ? Math.max(0, +agora - Date.parse(c.sla_desde)) : 0);
  const estourado = c.sla_limite_s ? ms > c.sla_limite_s * 1000 : false;
  return (
    <p className={`mt-3 text-sm ${estourado ? "text-red-700" : "text-zinc-600"}`}>
      SLA: {Math.round(ms / 1000)} s{c.sla_limite_s ? ` de ${c.sla_limite_s} s` : " (fila sem limite)"} ·{" "}
      {correndo ? "correndo (a operação deve resposta)" : "pausado (aguardando o cliente ou encerrada)"}
      {c.ouvidoria ? " · ouvidoria: preservada no expurgo" : ""}
    </p>
  );
}

/** Trace ponta a ponta de uma mensagem do cliente: canal, núcleo, broker/Kafka, agente e volta. */
function TraceMensagem({ idConversa, mensagens }: { idConversa: string; mensagens: Mensagem[] }) {
  const doCliente = mensagens.filter((m) => m.autor_tipo === "cliente");
  const [escolhida, setEscolhida] = useState<string>("");
  const [traco, setTraco] = useState<Traco | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const id = escolhida || doCliente[doCliente.length - 1]?.id || "";

  async function carregar() {
    setErro(null);
    try {
      setTraco(await apiGet<Traco>(`/conversas/${idConversa}/traco/${id}`));
    } catch (e) {
      setErro(textoDoErro(e));
    }
  }

  if (doCliente.length === 0) return null;
  return (
    <Cartao titulo="Trace ponta a ponta de uma mensagem">
      <div className="flex flex-wrap items-center gap-2">
        <select className="rounded border px-2 py-1 text-sm" value={id} onChange={(e) => setEscolhida(e.target.value)}>
          {doCliente.map((m) => (
            <option key={m.id} value={m.id}>
              #{m.seq} {m.conteudo.slice(0, 50)}
            </option>
          ))}
        </select>
        <button className="rounded bg-zinc-800 px-3 py-1 text-sm text-white" onClick={() => void carregar()}>
          Montar trace
        </button>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {traco && (
        <table className="mt-3 w-full text-left text-sm">
          <thead className="text-xs text-zinc-500">
            <tr>
              <th className="py-1">+ms</th>
              <th>onde</th>
              <th>o quê</th>
              <th>evento</th>
            </tr>
          </thead>
          <tbody>
            {traco.saltos.map((s, i) => (
              <tr key={i} className="border-t">
                <td className="py-1 font-mono">{s.ms}</td>
                <td>{s.onde}</td>
                <td>{s.o_que}</td>
                <td className="font-mono text-xs">{(s.id_evento ?? s.id_externo ?? "").slice(0, 8)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {traco && (
        <p className="mt-2 text-xs text-zinc-500">
          {traco.ponta_a_ponta_ms !== null
            ? `Da chegada à entrega ao cliente: ${traco.ponta_a_ponta_ms} ms.`
            : "A entrega ao cliente ainda não aparece no canal."}{" "}
          Os saltos estão ligados pelos ids do contrato (id_externo, id_evento, causado_por).
        </p>
      )}
    </Cartao>
  );
}
