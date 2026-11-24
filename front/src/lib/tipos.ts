// Tipos com os nomes de campo exatamente como a API devolve (nucleo/api/).

export type Marca = "infinitepay" | "jim";
export type Canal = "chat" | "whatsapp" | "email";
export type Estado = "nova" | "na_fila" | "com_ia" | "escalada" | "com_humano" | "resolvida";
export type AutorTipo = "cliente" | "ia" | "humano" | "sistema";

export interface MensagemAceita {
  id_conversa: string | null;
  id_mensagem: string | null;
  duplicada: boolean;
  estado: string | null;
}

export interface Conversa {
  id: string;
  id_cliente: string;
  marca: Marca;
  canal: Canal;
  estado: Estado;
  categoria: string | null;
  prioridade: number | null;
  sentimento: string | null;
  idioma: string | null;
  origem: string | null;
  id_fila: string | null;
  id_atendente: string | null;
  id_atribuicao_atual: string | null;
  versao_regras: number | null;
  criada_em: string;
  atualizada_em: string;
  resolvida_em: string | null;
  na_fila_desde: string | null;
  motivo_encerramento: string | null;
  sla_acumulado_ms?: number;
  sla_desde?: string | null;
  sla_limite_s?: number | null;
  ouvidoria?: boolean;
  cliente: string;
  atendente: string | null;
}

export interface SaltoTraco {
  onde: string;
  o_que: string;
  quando: string;
  ms: number;
  id_evento?: string;
  id_externo?: string | null;
  tentativas?: number;
  sequencia?: number;
}

export interface Traco {
  id_mensagem: string;
  id_externo: string | null;
  conteudo: string;
  eventos_ao_agente: string[];
  saltos: SaltoTraco[];
  ponta_a_ponta_ms: number | null;
}

export interface Mensagem {
  id: string;
  autor_tipo: AutorTipo;
  id_autor: string | null;
  conteudo: string;
  canal: string | null;
  id_externo: string | null;
  seq: number | null;
  criada_em: string;
}

export interface EventoAuditoria {
  tipo: string;
  ator_tipo: string;
  id_ator: string | null;
  id_atribuicao: string | null;
  payload: Record<string, unknown>;
  criado_em: string;
}

export interface Escala {
  motivo: string;
  resumo: string | null;
  fontes: string[] | null;
  reserva: boolean;
  prioridade: number | null;
  criada_em: string;
}

export interface Perfil {
  produtos: string[];
  segmento: string | null;
  contatos_30d: number;
  escalas_30d: number;
  canal_preferido: string | null;
  ultimo_assunto: { categoria: string; data: string } | null;
}

export interface DetalheConversa {
  conversa: Conversa;
  mensagens: Mensagem[];
  auditoria: EventoAuditoria[];
  escalas: Escala[];
  perfil: Perfil;
}

export interface ConversaResumo {
  id: string;
  marca: Marca;
  canal: Canal;
  estado: Estado;
  categoria: string | null;
  prioridade: number | null;
  sentimento: string | null;
  origem: string | null;
  id_fila: string | null;
  id_atendente: string | null;
  atendente: string | null;
  cliente: string;
  criada_em: string;
  atualizada_em: string;
}

export interface Atendente {
  id: string;
  tipo: "humano" | "ia";
  nome: string;
  marca: Marca;
  id_equipe: string;
  capacidade: number;
  ativas: number;
  status: string;
}

export interface ItemFila {
  id: string;
  marca: Marca;
  canal: Canal;
  estado: Estado;
  categoria: string | null;
  prioridade: number | null;
  sentimento: string | null;
  origem: string | null;
  id_fila: string | null;
  na_fila_desde: string | null;
  espera_s: number;
  cliente: string;
  motivo: string | null;
  resumo: string | null;
  fontes: string[] | null;
  reserva: boolean | null;
}

export interface ConversaDoAtendente {
  id: string;
  marca: Marca;
  canal: Canal;
  estado: Estado;
  categoria: string | null;
  prioridade: number | null;
  cliente: string;
  atualizada_em: string;
}

// Regras de filas
export type Operador = "igual" | "diferente" | "em";
export type ValorCondicao = string | number | (string | number)[];

export interface Condicao {
  campo: string;
  operador: Operador;
  valor: ValorCondicao;
}

export type Condicoes = { todas: Condicao[] } | { qualquer: Condicao[] } | Record<string, never>;

export interface Grupo {
  tipo: "ia" | "equipe";
  id: string;
}

export interface Fila {
  id: string;
  nome: string;
  ordem: number;
  prioridade: number;
  ativa: boolean;
  ao_abrir_disjuntor?: "reter" | "transbordar";
  condicoes: Condicoes;
  atendentes: Grupo[];
}

export interface Regras {
  fila_padrao: string;
  filas: Fila[];
}

export interface VersaoAtiva {
  numero: number;
  filas: Regras;
  ativada_em: string | null;
}

export interface Versao {
  numero: number;
  ativa: boolean;
  criada_por: string;
  criada_em: string;
  ativada_em: string | null;
  filas: Regras;
}

export interface Validacao {
  valida: boolean;
  erros: string[];
}

export interface Simulacao {
  fila: string;
  regra: Condicao[] | "fila_padrao";
  versao: number;
}

// Supervisor
export interface Metricas {
  conversas_por_estado: Record<string, number>;
  filas: { id_fila: string; tamanho: number; espera_max_s: number }[];
  escalas_ultima_hora: Record<string, number>;
  outbox: Record<string, number>;
  atendentes: Omit<Atendente, "id">[];
  descartes_fencing_ultima_hora: number;
  resolvidas_ultima_hora: { pela_ia: number; total: number };
  chaves: Record<string, boolean | number>;
}

export interface ErroOutbox {
  id: number;
  id_conversa: string | null;
  destino: string;
  tentativas: number;
  ultimo_erro: string | null;
  criado_em: string;
}

export type Reconciliacao = Record<string, { total: number; exemplos: string[] }>;
