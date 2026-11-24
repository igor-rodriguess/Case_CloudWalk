export function hora(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function dataHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function duracao(segundos: number | null | undefined): string {
  if (segundos === null || segundos === undefined) return "—";
  if (segundos < 60) return `${segundos} s`;
  const m = Math.floor(segundos / 60);
  if (m < 60) return `${m} min ${segundos % 60} s`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}

export function curto(id: string | null | undefined): string {
  return id ? id.slice(0, 8) : "—";
}

export const ROTULO_ESTADO: Record<string, string> = {
  nova: "nova",
  na_fila: "na fila",
  com_ia: "com a IA",
  escalada: "escalada",
  com_humano: "com analista",
  resolvida: "resolvida",
};

export const COR_ESTADO: Record<string, string> = {
  nova: "bg-zinc-100 text-zinc-700",
  na_fila: "bg-amber-100 text-amber-800",
  com_ia: "bg-sky-100 text-sky-800",
  escalada: "bg-red-100 text-red-800",
  com_humano: "bg-violet-100 text-violet-800",
  resolvida: "bg-emerald-100 text-emerald-800",
};

export const ROTULO_AUTOR: Record<string, string> = {
  cliente: "Cliente",
  ia: "IA",
  humano: "Analista",
  sistema: "Sistema",
};

export const ESTADOS = ["nova", "na_fila", "com_ia", "escalada", "com_humano", "resolvida"] as const;
export const MARCAS = ["infinitepay", "jim"] as const;
export const CANAIS = ["chat", "whatsapp", "email"] as const;
