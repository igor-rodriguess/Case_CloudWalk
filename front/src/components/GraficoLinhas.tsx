"use client";

import { useEffect, useRef, useState } from "react";
import { decimal } from "@/lib/formatar";

export interface Serie {
  chave: string;
  nome: string;
  cor: string;
}

export interface Ponto {
  t: string;
  [chave: string]: number | string | null;
}

const ALTURA = 260;
const MARGEM = { topo: 16, direita: 96, base: 28, esquerda: 44 };

/** Divide o máximo em ~4 passos "redondos" para o eixo y. */
function passosY(maximo: number): number[] {
  if (maximo <= 0) return [0, 1];
  const bruto = maximo / 4;
  const magnitude = 10 ** Math.floor(Math.log10(bruto));
  const passo = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((p) => p >= bruto) ?? bruto;
  const topo = Math.ceil(maximo / passo) * passo;
  return Array.from({ length: Math.round(topo / passo) + 1 }, (_, i) => +(i * passo).toFixed(6));
}

function hora(t: string): string {
  return new Date(t).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/**
 * Gráfico de linhas em SVG, um eixo só: linhas de 2 px, grade recessiva, rótulo direto no fim de
 * cada série (identidade nunca só pela cor), cursor com tooltip e alternância para tabela.
 */
export function GraficoLinhas({ pontos, series, unidade, formatar = (v) => decimal(v) }: {
  pontos: Ponto[];
  series: Serie[];
  unidade: string;
  formatar?: (v: number) => string;
}) {
  const caixa = useRef<HTMLDivElement>(null);
  const [largura, setLargura] = useState(800);
  const [foco, setFoco] = useState<number | null>(null);
  const [tabela, setTabela] = useState(false);

  useEffect(() => {
    const el = caixa.current;
    if (!el) return;
    const obs = new ResizeObserver(([e]) => setLargura(Math.max(320, e.contentRect.width)));
    obs.observe(el);
    return () => obs.disconnect();
  }, [tabela]);

  const valores = pontos.flatMap((p) => series.map((s) => Number(p[s.chave] ?? 0)));
  const ys = passosY(Math.max(0, ...valores));
  const topoY = ys[ys.length - 1] || 1;
  const w = largura - MARGEM.esquerda - MARGEM.direita;
  const h = ALTURA - MARGEM.topo - MARGEM.base;
  const x = (i: number) => MARGEM.esquerda + (pontos.length <= 1 ? 0 : (i / (pontos.length - 1)) * w);
  const y = (v: number) => MARGEM.topo + h - (v / topoY) * h;
  const marcasX = pontos.length > 1 ? [0, Math.floor((pontos.length - 1) / 2), pontos.length - 1] : [0];

  // valor ausente (null) vira lacuna na linha, nunca zero
  function caminho(chave: string): string {
    let novo = true;
    return pontos
      .map((p, i) => {
        if (p[chave] === null || p[chave] === undefined) {
          novo = true;
          return "";
        }
        const trecho = `${novo ? "M" : "L"}${x(i).toFixed(1)},${y(Number(p[chave])).toFixed(1)}`;
        novo = false;
        return trecho;
      })
      .join(" ");
  }

  function ultimo(chave: string): { i: number; v: number } | null {
    for (let i = pontos.length - 1; i >= 0; i--) {
      if (pontos[i][chave] !== null && pontos[i][chave] !== undefined) return { i, v: Number(pontos[i][chave]) };
    }
    return null;
  }

  function aoMover(e: React.MouseEvent<SVGRectElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const rel = (e.clientX - r.left) / r.width;
    setFoco(Math.max(0, Math.min(pontos.length - 1, Math.round(rel * (pontos.length - 1)))));
  }

  // rótulos diretos no fim das linhas, afastados para não colidirem
  const finais = series
    .map((s) => ({ s, u: ultimo(s.chave) }))
    .filter((f): f is { s: Serie; u: { i: number; v: number } } => f.u !== null)
    .map(({ s, u }) => ({ s, v: u.v, i: u.i }))
    .sort((a, b) => b.v - a.v)
    .reduce<{ s: Serie; v: number; i: number; py: number }[]>((acc, item) => {
      let py = y(item.v);
      const anterior = acc[acc.length - 1];
      if (anterior && py - anterior.py < 14) py = anterior.py + 14;
      acc.push({ ...item, py });
      return acc;
    }, []);
  // se a pilha de rótulos passar da base do gráfico, sobe a pilha inteira
  const excesso = finais.length ? finais[finais.length - 1].py - (MARGEM.topo + h) : 0;
  if (excesso > 0) finais.forEach((f) => (f.py -= excesso));

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-4">
          {series.length > 1 && series.map((s) => (
            <span key={s.chave} className="flex items-center gap-1.5 text-xs text-zinc-600">
              <span className="inline-block h-0.5 w-4 rounded" style={{ background: s.cor }} />
              {s.nome}
            </span>
          ))}
        </div>
        <button className="font-mono text-[11px] text-zinc-500 hover:text-zinc-800" onClick={() => setTabela(!tabela)}>
          {tabela ? "ver gráfico" : "ver tabela"}
        </button>
      </div>

      {tabela ? (
        <div className="max-h-64 overflow-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead className="sticky top-0 bg-white text-zinc-500">
              <tr>
                <th className="py-1">hora</th>
                {series.map((s) => (
                  <th key={s.chave}>{s.nome} ({unidade})</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...pontos].reverse().map((p) => (
                <tr key={p.t} className="border-t border-zinc-200">
                  <td className="py-1 text-zinc-500">{hora(p.t)}</td>
                  {series.map((s) => (
                    <td key={s.chave}>{p[s.chave] === null ? "—" : formatar(Number(p[s.chave]))}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div ref={caixa} className="relative w-full">
          <svg width={largura} height={ALTURA} role="img" aria-label={`Gráfico de ${series.map((s) => s.nome).join(", ")}`}>
            {ys.map((v) => (
              <g key={v}>
                <line x1={MARGEM.esquerda} x2={MARGEM.esquerda + w} y1={y(v)} y2={y(v)} stroke="#ffffff14" />
                <text x={MARGEM.esquerda - 8} y={y(v) + 3} textAnchor="end" className="fill-zinc-500 font-mono text-[10px]">
                  {formatar(v)}
                </text>
              </g>
            ))}
            {marcasX.map((i) => (
              <text key={i} x={x(i)} y={ALTURA - 8} textAnchor={i === 0 ? "start" : i === pontos.length - 1 ? "end" : "middle"}
                className="fill-zinc-500 font-mono text-[10px]">
                {pontos[i] ? hora(pontos[i].t) : ""}
              </text>
            ))}
            {series.map((s) => (
              <path key={s.chave} d={caminho(s.chave)} fill="none" stroke={s.cor} strokeWidth={2}
                strokeLinejoin="round" strokeLinecap="round" />
            ))}
            {finais.map(({ s, v, i, py }) => (
              <g key={s.chave}>
                <circle cx={x(i)} cy={y(v)} r={4} fill={s.cor} stroke="#141414" strokeWidth={2} />
                <text x={x(pontos.length - 1) + 10} y={py + 3} className="fill-zinc-700 font-mono text-[10px]">
                  {s.nome} {formatar(v)}
                </text>
              </g>
            ))}
            {foco !== null && pontos[foco] && (
              <g>
                <line x1={x(foco)} x2={x(foco)} y1={MARGEM.topo} y2={MARGEM.topo + h} stroke="#ffffff40" />
                {series.filter((s) => pontos[foco][s.chave] !== null).map((s) => (
                  <circle key={s.chave} cx={x(foco)} cy={y(Number(pontos[foco][s.chave] ?? 0))} r={4} fill={s.cor}
                    stroke="#141414" strokeWidth={2} />
                ))}
              </g>
            )}
            <rect x={MARGEM.esquerda} y={MARGEM.topo} width={w} height={h} fill="transparent"
              onMouseMove={aoMover} onMouseLeave={() => setFoco(null)} />
          </svg>
          {foco !== null && pontos[foco] && (
            <div
              className="pointer-events-none absolute top-2 rounded border border-zinc-300 bg-black/90 px-3 py-2 font-mono text-[11px] shadow-lg"
              style={{ left: Math.min(x(foco) + 12, largura - 190) }}
            >
              <div className="mb-1 text-zinc-500">{hora(pontos[foco].t)}</div>
              {series.map((s) => (
                <div key={s.chave} className="flex items-center gap-2 text-zinc-800">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ background: s.cor }} />
                  {s.nome}: {pontos[foco][s.chave] === null ? "—" : `${formatar(Number(pontos[foco][s.chave]))} ${unidade}`}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
