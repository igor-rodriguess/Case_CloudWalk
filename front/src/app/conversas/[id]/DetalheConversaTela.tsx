"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import {
  CabecalhoConversa,
  Historico,
  LinhaDoTempo,
  ListaEscalas,
  PerfilCliente,
  useNomesAtendentes,
} from "@/components/conversa";
import { Atualizado, Aviso, Cartao } from "@/components/ui";
import type { DetalheConversa } from "@/lib/tipos";
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
          </Cartao>

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
