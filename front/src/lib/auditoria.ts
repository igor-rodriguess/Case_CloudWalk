// Traduz cada evento de auditoria (tabela eventos) em uma frase com o porquê da decisão.
import type { EventoAuditoria } from "./tipos";

type Payload = Record<string, unknown>;
type Nomes = Record<string, string>;

const MOTIVO: Record<string, string> = {
  timeout_agente: "o agente não respondeu dentro do prazo",
  pedido_do_cliente: "o cliente pediu um atendente humano",
  agente: "o agente decidiu escalar",
  analista_assumiu: "o analista assumiu",
  devolvida: "o analista devolveu para a IA",
  resolvida: "conversa encerrada",
  atribuicao_vencida: "a atribuição já não era a vigente (fencing)",
  preferencia_e_menor_ocupacao: "grupo preferido da fila e menor ocupação",
  sem_candidato: "nenhum atendente com capacidade",
};

function motivo(m: unknown): string {
  if (m === null || m === undefined || m === "") return "";
  const t = String(m);
  return MOTIVO[t] ? `${t} (${MOTIVO[t]})` : t;
}

function nome(id: unknown, nomes: Nomes): string {
  if (typeof id !== "string") return "ninguém";
  return nomes[id] ?? id.slice(0, 8);
}

function regraEmTexto(regra: unknown): string {
  if (regra === "fila_padrao") return "nenhuma fila casou, foi para a fila padrão";
  if (!Array.isArray(regra)) return JSON.stringify(regra);
  if (regra.length === 0) return "fila sem condições";
  return (
    "casou " +
    regra
      .map((c: { campo: string; operador: string; valor: unknown }) => `${c.campo} ${c.operador} ${JSON.stringify(c.valor)}`)
      .join(" e ")
  );
}

export interface Explicacao {
  titulo: string;
  porque: string;
  alerta?: boolean;
}

export function explicar(ev: EventoAuditoria, nomes: Nomes): Explicacao {
  const p: Payload = ev.payload ?? {};
  switch (ev.tipo) {
    case "triagem":
      return {
        titulo: "Triagem",
        porque: `categoria ${p.categoria}, prioridade ${p.prioridade}, sentimento ${p.sentimento}, idioma ${p.idioma} (palavras-chave da primeira mensagem)`,
      };
    case "decisao_roteamento":
      return {
        titulo: `Roteamento para ${p.fila}`,
        porque: `regras v${p.versao}: ${regraEmTexto(p.regra)}`,
      };
    case "decisao_distribuicao": {
      const candidatos = Array.isArray(p.candidatos) ? p.candidatos.length : 0;
      return {
        titulo: p.escolhido ? `Distribuída para ${nome(p.escolhido, nomes)}` : "Distribuição sem atendente",
        porque: `fila ${p.fila}; ${motivo(p.motivo)}; ${candidatos} candidato(s) avaliado(s)`,
        alerta: !p.escolhido,
      };
    }
    case "transicao": {
      const saidas = Array.isArray(p.saidas) && p.saidas.length ? `; saídas: ${p.saidas.join(", ")}` : "";
      const m = motivo(p.motivo);
      return {
        titulo: `Estado: ${p.para}`,
        porque: (m ? `motivo: ${m}` : "sem motivo registrado") + saidas,
        alerta: p.para === "escalada",
      };
    }
    case "mensagem": {
      const saidas = Array.isArray(p.saidas) && p.saidas.length ? `saídas: ${p.saidas.join(", ")}` : "sem saída (fica no histórico)";
      return { titulo: `Mensagem de ${ev.ator_tipo}`, porque: saidas };
    }
    case "evento_descartado":
      return {
        titulo: "Evento descartado pelo fencing",
        porque: `chegou com a atribuição ${String(ev.id_atribuicao ?? "").slice(0, 8)}, vigente era ${String(p.atual ?? "nenhuma").slice(0, 8)}; ${motivo(p.motivo)}`,
        alerta: true,
      };
    case "transicao_invalida":
      return { titulo: "Transição rejeitada", porque: `de ${p.de} para ${p.para} não é permitida`, alerta: true };
    case "sem_capacidade":
      return { titulo: "Sem capacidade", porque: `${nome(p.atendente, nomes)} está no limite de conversas`, alerta: true };
    case "evento_desconhecido":
      return { titulo: "Evento de tipo desconhecido", porque: `tipo ${p.tipo_recebido}, versão ${p.versao}` };
    default:
      return { titulo: ev.tipo, porque: JSON.stringify(p) };
  }
}
