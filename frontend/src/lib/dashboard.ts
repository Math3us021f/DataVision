import type { Agg, ChartType, ColumnProfile, FilterOp, FilterSpec, QuerySpec, TimeGrain } from "@/types";

export const MAX_WIDGETS = 12; // mesmo limite do servidor
export const QUERY_LIMIT = 20;

export const AGG_LABELS: Record<Agg, string> = {
  sum: "Soma",
  mean: "Média",
  count: "Contagem",
  min: "Mínimo",
  max: "Máximo",
  count_distinct: "Valores distintos",
};
export const CHART_LABELS: Record<ChartType, string> = { bar: "Barras", line: "Linha", pie: "Pizza", kpi: "Indicador" };
export const GRAIN_LABELS: Record<TimeGrain, string> = { day: "Dia", month: "Mês", year: "Ano" };
export const OP_LABELS: Record<FilterOp, string> = {
  eq: "é igual a",
  ne: "é diferente de",
  gt: ">",
  gte: "≥",
  lt: "<",
  lte: "≤",
  contains: "contém",
  in: "é um de (separe por vírgula)",
};

const NUMERIC = new Set(["integer", "float"]);
const NUMERIC_AGGS: Agg[] = ["sum", "mean", "count", "min", "max", "count_distinct"];
const OTHER_AGGS: Agg[] = ["count", "count_distinct"];

export type FilterKind = "text" | "number" | "datetime" | "boolean";
const OPS_BY_KIND: Record<FilterKind, FilterOp[]> = {
  text: ["eq", "ne", "contains", "in"],
  number: ["eq", "ne", "gt", "gte", "lt", "lte", "in"],
  datetime: ["eq", "ne", "gt", "gte", "lt", "lte"],
  boolean: ["eq", "ne"],
};

/** O que o usuário configura num gráfico (um subconjunto da spec que a API aceita). */
export interface WidgetConfig {
  chart: ChartType;
  dimension: string;
  grain: TimeGrain;
  metricColumn: string;
  agg: Agg;
}

export type Columns = ColumnProfile[];

export const typeOf = (columns: Columns, name: string): string => columns.find((c) => c.column_name === name)?.inferred_type ?? "text";
export const filterKindOf = (columns: Columns, name: string): FilterKind => {
  const type = typeOf(columns, name);
  return NUMERIC.has(type) ? "number" : type === "datetime" ? "datetime" : type === "boolean" ? "boolean" : "text";
};
export const opsFor = (kind: FilterKind): FilterOp[] => OPS_BY_KIND[kind];
export const allowedAggs = (columns: Columns, metricColumn: string): Agg[] =>
  NUMERIC.has(typeOf(columns, metricColumn)) ? NUMERIC_AGGS : OTHER_AGGS;

export function defaultDimension(columns: Columns): string {
  const preferred =
    columns.find((c) => c.inferred_type === "datetime") ?? columns.find((c) => c.inferred_type === "text") ?? columns[0];
  return preferred.column_name;
}

export function configFromSpec(spec: QuerySpec, columns: Columns): WidgetConfig {
  return {
    chart: spec.chart,
    dimension: spec.dimension?.column ?? defaultDimension(columns),
    grain: spec.dimension?.time_grain ?? "month",
    metricColumn: spec.metrics[0].column,
    agg: spec.metrics[0].agg,
  };
}

export function specFromConfig(config: WidgetConfig, columns: Columns, filters: FilterSpec[]): QuerySpec {
  const spec: QuerySpec = {
    chart: config.chart,
    metrics: [{ column: config.metricColumn, agg: config.agg }],
    filters,
    limit: QUERY_LIMIT,
  };
  if (config.chart !== "kpi") {
    spec.dimension = {
      column: config.dimension,
      time_grain: typeOf(columns, config.dimension) === "datetime" ? config.grain : null,
    };
  }
  return spec;
}

export function autoTitle(config: WidgetConfig, columns: Columns): string {
  const measure = `${AGG_LABELS[config.agg]} de ${config.metricColumn}`;
  if (config.chart === "kpi") return measure;
  const grain = typeOf(columns, config.dimension) === "datetime" ? ` (${GRAIN_LABELS[config.grain].toLowerCase()})` : "";
  return `${measure} por ${config.dimension}${grain}`;
}

export function newWidgetConfig(columns: Columns): WidgetConfig {
  const dimension = defaultDimension(columns);
  const measure = columns.find((c) => NUMERIC.has(c.inferred_type));
  return {
    chart: "bar",
    dimension,
    grain: "month",
    metricColumn: measure?.column_name ?? dimension,
    agg: measure ? "sum" : "count",
  };
}

/** Filtro como o usuário edita: texto cru nos campos. */
export interface FilterDraft {
  id: number;
  column: string;
  op: FilterOp;
  raw: string;
}

/** Valor digitado → valor da spec (ou null se ainda incompleto/inválido, e então o filtro é ignorado). */
export function filterToSpec(draft: FilterDraft, columns: Columns): FilterSpec | null {
  const kind = filterKindOf(columns, draft.column);
  const raw = draft.raw.trim();
  if (raw === "") return null;

  if (draft.op === "in") {
    const parts = raw.split(",").map((s) => s.trim()).filter(Boolean);
    if (parts.length === 0) return null;
    if (kind === "number") {
      const numbers = parts.map(Number);
      return numbers.every(Number.isFinite) ? { column: draft.column, op: "in", value: numbers } : null;
    }
    return { column: draft.column, op: "in", value: parts };
  }
  if (kind === "number") {
    const n = Number(raw);
    return Number.isFinite(n) ? { column: draft.column, op: draft.op, value: n } : null;
  }
  if (kind === "boolean") return { column: draft.column, op: draft.op, value: raw === "true" };
  return { column: draft.column, op: draft.op, value: raw };
}

/** Valor salvo → texto do campo, como o usuário digitaria. */
export const rawFromValue = (value: FilterSpec["value"]): string => (Array.isArray(value) ? value.join(", ") : String(value));
