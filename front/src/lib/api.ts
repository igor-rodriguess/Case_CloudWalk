// Cliente da API do núcleo. A URL vem de NEXT_PUBLIC_API_URL (padrão http://localhost:8000).

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ErroApi extends Error {
  constructor(
    public status: number,
    message: string,
    public detalhe: unknown,
  ) {
    super(message);
  }
}

// FastAPI devolve {detail: string | {erros: [...]} | [{loc, msg}]}.
function mensagemDoDetalhe(status: number, corpo: unknown): string {
  const detail = (corpo as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return `${status}: ${detail}`;
  if (Array.isArray(detail)) {
    return `${status}: ` + detail.map((d) => `${(d.loc ?? []).join(".")} ${d.msg}`).join("; ");
  }
  if (detail && typeof detail === "object" && "erros" in detail) {
    return `${status}: ` + (detail as { erros: string[] }).erros.join("; ");
  }
  return `${status}: ${JSON.stringify(corpo)}`;
}

async function requisitar<T>(caminho: string, init: RequestInit): Promise<T> {
  const r = await fetch(`${API_URL}${caminho}`, { ...init, cache: "no-store" });
  const texto = await r.text();
  const corpo = texto ? JSON.parse(texto) : null;
  if (!r.ok) throw new ErroApi(r.status, mensagemDoDetalhe(r.status, corpo), corpo);
  return corpo as T;
}

export function apiGet<T>(caminho: string, signal?: AbortSignal): Promise<T> {
  return requisitar<T>(caminho, { method: "GET", signal });
}

export function apiPost<T>(caminho: string, corpo: unknown): Promise<T> {
  return requisitar<T>(caminho, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
}

export function textoDoErro(e: unknown): string {
  if (e instanceof ErroApi) return e.message;
  if (e instanceof Error) return `sem resposta da API (${e.message})`;
  return String(e);
}
