"use client";

import {
  CAMPOS,
  combinacao,
  converterValor,
  listaCondicoes,
  montarCondicoes,
  novaFila,
  OPERADORES,
  VALORES,
  valorEmTexto,
  type Combinacao,
} from "@/lib/regras";
import type { Condicao, Fila, Grupo, Operador, Regras } from "@/lib/tipos";
import { Botao, campo, Rotulo } from "./ui";

const pequeno = `${campo} py-1 text-xs`;

export function EditorFilas({ regras, grupos, onChange }: {
  regras: Regras;
  grupos: Grupo[];
  onChange: (r: Regras) => void;
}) {
  const ids = regras.filas.map((f) => f.id);

  function trocarFila(i: number, f: Fila) {
    const filas = [...regras.filas];
    const idAntigo = filas[i].id;
    filas[i] = f;
    const fila_padrao = regras.fila_padrao === idAntigo ? f.id : regras.fila_padrao;
    onChange({ ...regras, filas, fila_padrao });
  }

  function remover(i: number) {
    onChange({ ...regras, filas: regras.filas.filter((_, j) => j !== i) });
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <Rotulo texto="Fila padrão (quando nenhuma regra casa)">
          <select className={campo} value={regras.fila_padrao} onChange={(e) => onChange({ ...regras, fila_padrao: e.target.value })}>
            {!ids.includes(regras.fila_padrao) && <option value={regras.fila_padrao}>{regras.fila_padrao} (não existe)</option>}
            {ids.map((id) => (
              <option key={id} value={id}>{id}</option>
            ))}
          </select>
        </Rotulo>
        <Botao variante="secundario" onClick={() => onChange({ ...regras, filas: [...regras.filas].sort((a, b) => a.ordem - b.ordem) })}>
          Ordenar pela ordem
        </Botao>
        <Botao variante="secundario" onClick={() => onChange({ ...regras, filas: [...regras.filas, novaFila(regras.filas)] })}>
          Adicionar fila
        </Botao>
      </div>
      <p className="text-xs text-zinc-500">
        O roteador testa as filas ativas pela ordem; a primeira cujas condições casam leva a conversa. Os grupos de
        atendentes valem na ordem da lista (o primeiro é o preferido).
      </p>
      {regras.filas.map((f, i) => (
        <EditorFila
          key={i}
          fila={f}
          padrao={f.id === regras.fila_padrao}
          grupos={grupos}
          onChange={(nova) => trocarFila(i, nova)}
          onRemover={() => remover(i)}
        />
      ))}
    </div>
  );
}

function EditorFila({ fila, padrao, grupos, onChange, onRemover }: {
  fila: Fila;
  padrao: boolean;
  grupos: Grupo[];
  onChange: (f: Fila) => void;
  onRemover: () => void;
}) {
  const tipo = combinacao(fila.condicoes);
  const lista = listaCondicoes(fila.condicoes);

  function trocarCondicoes(t: Combinacao, l: Condicao[]) {
    onChange({ ...fila, condicoes: montarCondicoes(t, l) });
  }

  function trocarCondicao(i: number, c: Condicao) {
    const l = [...lista];
    l[i] = c;
    trocarCondicoes(tipo, l);
  }

  function trocarOperador(i: number, c: Condicao, operador: Operador) {
    let valor = c.valor;
    if (operador === "em" && !Array.isArray(valor)) valor = valor === "" ? [] : [valor];
    if (operador !== "em" && Array.isArray(valor)) valor = valor[0] ?? "";
    trocarCondicao(i, { ...c, operador, valor });
  }

  function moverGrupo(i: number, delta: number) {
    const a = [...fila.atendentes];
    const j = i + delta;
    if (j < 0 || j >= a.length) return;
    [a[i], a[j]] = [a[j], a[i]];
    onChange({ ...fila, atendentes: a });
  }

  const disponiveis = grupos.filter((g) => !fila.atendentes.some((a) => a.tipo === g.tipo && a.id === g.id));

  return (
    <div className={`rounded border p-3 ${fila.ativa ? "border-zinc-200" : "border-dashed border-zinc-300 bg-zinc-50"}`}>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
        <Rotulo texto="Id">
          <input className={pequeno} value={fila.id} onChange={(e) => onChange({ ...fila, id: e.target.value })} />
        </Rotulo>
        <div className="col-span-1 md:col-span-2">
          <Rotulo texto="Nome">
            <input className={`${pequeno} w-full`} value={fila.nome} onChange={(e) => onChange({ ...fila, nome: e.target.value })} />
          </Rotulo>
        </div>
        <Rotulo texto="Ordem">
          <input
            type="number"
            className={pequeno}
            value={fila.ordem}
            onChange={(e) => onChange({ ...fila, ordem: Number(e.target.value) })}
          />
        </Rotulo>
        <Rotulo texto="Prioridade">
          <select className={pequeno} value={fila.prioridade} onChange={(e) => onChange({ ...fila, prioridade: Number(e.target.value) })}>
            {[1, 2, 3].map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </Rotulo>
        <Rotulo texto="Disjuntor aberto">
          <select
            className={pequeno}
            value={fila.ao_abrir_disjuntor ?? "reter"}
            onChange={(e) => onChange({ ...fila, ao_abrir_disjuntor: e.target.value as Fila["ao_abrir_disjuntor"] })}
          >
            <option value="reter">reter</option>
            <option value="transbordar">transbordar</option>
          </select>
        </Rotulo>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-4 text-xs">
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={fila.ativa} onChange={(e) => onChange({ ...fila, ativa: e.target.checked })} />
          ativa
        </label>
        {padrao && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800">fila padrão</span>}
        <button type="button" className="ml-auto text-red-700 hover:underline" onClick={onRemover}>
          remover fila
        </button>
      </div>

      <div className="mt-3 grid gap-3 2xl:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2 text-xs font-medium text-zinc-600">
            Condições
            <select className={pequeno} value={tipo} onChange={(e) => trocarCondicoes(e.target.value as Combinacao, lista)}>
              <option value="todas">todas (E)</option>
              <option value="qualquer">qualquer (OU)</option>
              <option value="nenhuma">sem condições (casa tudo)</option>
            </select>
          </div>
          {tipo !== "nenhuma" && (
            <>
              {lista.map((c, i) => (
                <div key={i} className="flex flex-wrap items-center gap-1.5">
                  <select className={pequeno} value={c.campo} onChange={(e) => trocarCondicao(i, { ...c, campo: e.target.value })}>
                    {!CAMPOS.includes(c.campo as (typeof CAMPOS)[number]) && <option value={c.campo}>{c.campo}</option>}
                    {CAMPOS.map((x) => (
                      <option key={x} value={x}>{x}</option>
                    ))}
                  </select>
                  <select className={pequeno} value={c.operador} onChange={(e) => trocarOperador(i, c, e.target.value as Operador)}>
                    {OPERADORES.map((x) => (
                      <option key={x} value={x}>{x}</option>
                    ))}
                  </select>
                  <input
                    className={`${pequeno} min-w-32 flex-1`}
                    list={`valores-${c.campo}`}
                    placeholder={c.operador === "em" ? "valores separados por vírgula" : "valor"}
                    value={valorEmTexto(c.valor)}
                    onChange={(e) => trocarCondicao(i, { ...c, valor: converterValor(c.campo, c.operador, e.target.value) })}
                  />
                  <button
                    type="button"
                    className="text-xs text-zinc-500 hover:text-red-700"
                    onClick={() => trocarCondicoes(tipo, lista.filter((_, j) => j !== i))}
                  >
                    remover
                  </button>
                </div>
              ))}
              <div>
                <button
                  type="button"
                  className="text-xs text-sky-700 hover:underline"
                  onClick={() => trocarCondicoes(tipo, [...lista, { campo: "marca", operador: "igual", valor: "infinitepay" }])}
                >
                  + condição
                </button>
              </div>
            </>
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-zinc-600">Grupos de atendentes (ordem de preferência)</span>
          {fila.atendentes.map((g, i) => (
            <div key={`${g.tipo}:${g.id}`} className="flex items-center gap-2 text-sm">
              <span className="w-5 text-xs text-zinc-400">{i + 1}.</span>
              <span className={`rounded px-1.5 py-0.5 text-xs ${g.tipo === "ia" ? "bg-sky-100 text-sky-800" : "bg-violet-100 text-violet-800"}`}>
                {g.tipo}
              </span>
              <span className="flex-1">{g.id}</span>
              <button type="button" className="text-xs text-zinc-500" onClick={() => moverGrupo(i, -1)} title="subir">↑</button>
              <button type="button" className="text-xs text-zinc-500" onClick={() => moverGrupo(i, 1)} title="descer">↓</button>
              <button
                type="button"
                className="text-xs text-zinc-500 hover:text-red-700"
                onClick={() => onChange({ ...fila, atendentes: fila.atendentes.filter((_, j) => j !== i) })}
              >
                remover
              </button>
            </div>
          ))}
          {disponiveis.length > 0 && (
            <select
              className={pequeno}
              value=""
              onChange={(e) => {
                const g = disponiveis.find((x) => `${x.tipo}:${x.id}` === e.target.value);
                if (g) onChange({ ...fila, atendentes: [...fila.atendentes, g] });
              }}
            >
              <option value="">+ adicionar grupo</option>
              {disponiveis.map((g) => (
                <option key={`${g.tipo}:${g.id}`} value={`${g.tipo}:${g.id}`}>
                  {g.tipo}: {g.id}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>
    </div>
  );
}

/** datalists com os valores aceitos por campo, usados pelos inputs de condição. */
export function ListasDeValores() {
  return (
    <>
      {Object.entries(VALORES).map(([c, vs]) => (
        <datalist key={c} id={`valores-${c}`}>
          {vs.map((v) => (
            <option key={String(v)} value={String(v)} />
          ))}
        </datalist>
      ))}
    </>
  );
}
