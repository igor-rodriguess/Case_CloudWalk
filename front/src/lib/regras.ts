// Vocabulário das regras de filas, igual a nucleo/dominio/roteador.py e triagem.py.
import type { Condicao, Condicoes, Fila, Regras, ValorCondicao } from "./tipos";

export const CAMPOS = ["marca", "canal", "categoria", "prioridade", "idioma", "segmento_cliente", "sentimento", "origem"] as const;
export const OPERADORES = ["igual", "diferente", "em"] as const;

export const VALORES: Record<string, (string | number)[]> = {
  marca: ["infinitepay", "jim"],
  canal: ["chat", "whatsapp", "email"],
  categoria: ["fraude", "credito", "repasse", "maquininha", "conta", "geral"],
  prioridade: [1, 2, 3],
  idioma: ["pt", "en"],
  segmento_cliente: ["pme"],
  sentimento: ["neutro", "negativo"],
  origem: ["cliente", "escalado"],
};

export type Combinacao = "todas" | "qualquer" | "nenhuma";

export function combinacao(c: Condicoes): Combinacao {
  if ("todas" in c) return "todas";
  if ("qualquer" in c) return "qualquer";
  return "nenhuma";
}

export function listaCondicoes(c: Condicoes): Condicao[] {
  if ("todas" in c) return c.todas;
  if ("qualquer" in c) return c.qualquer;
  return [];
}

export function montarCondicoes(tipo: Combinacao, lista: Condicao[]): Condicoes {
  if (tipo === "todas") return { todas: lista };
  if (tipo === "qualquer") return { qualquer: lista };
  return {};
}

function converterUm(campo: string, v: string): string | number {
  const t = v.trim();
  if (campo === "prioridade" && t !== "" && !Number.isNaN(Number(t))) return Number(t);
  return t;
}

/** Texto digitado -> valor da condição. Com `em`, lista separada por vírgula. */
export function converterValor(campo: string, operador: string, texto: string): ValorCondicao {
  if (operador === "em") return texto.split(",").map((v) => converterUm(campo, v));
  return converterUm(campo, texto);
}

export function valorEmTexto(valor: ValorCondicao): string {
  return Array.isArray(valor) ? valor.join(", ") : String(valor ?? "");
}

/** Tira itens vazios das listas de `em` antes de validar ou salvar. */
export function limpar(regras: Regras): Regras {
  return {
    ...regras,
    filas: regras.filas.map((f) => {
      const tipo = combinacao(f.condicoes);
      const lista = listaCondicoes(f.condicoes).map((c) =>
        Array.isArray(c.valor) ? { ...c, valor: c.valor.filter((v) => v !== "") } : c,
      );
      return { ...f, condicoes: montarCondicoes(tipo, lista) };
    }),
  };
}

export function novaFila(filas: Fila[]): Fila {
  const ordem = Math.max(0, ...filas.map((f) => Number(f.ordem) || 0)) + 1;
  let n = filas.length + 1;
  while (filas.some((f) => f.id === `nova-fila-${n}`)) n++;
  return {
    id: `nova-fila-${n}`,
    nome: "Nova fila",
    ordem,
    prioridade: 1,
    ativa: true,
    ao_abrir_disjuntor: "reter",
    condicoes: { todas: [] },
    atendentes: [],
  };
}
