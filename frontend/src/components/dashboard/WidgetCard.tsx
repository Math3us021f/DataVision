import { ChartColumn, ChartLine, ChartPie, Hash, Loader2, SlidersHorizontal, X, type LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { formatValue, QueryChart } from "@/components/charts/QueryChart";
import { Card } from "@/components/ui/card";
import { Field, Select } from "@/components/ui/select";
import { ApiError, api } from "@/lib/api";
import {
  AGG_LABELS,
  allowedAggs,
  autoTitle,
  CHART_LABELS,
  GRAIN_LABELS,
  specFromConfig,
  typeOf,
  type Columns,
  type WidgetConfig,
} from "@/lib/dashboard";
import { cn, formatNumber } from "@/lib/utils";
import type { Agg, ChartType, FilterSpec, QueryResult, TimeGrain } from "@/types";

const CHART_ICONS: Record<ChartType, LucideIcon> = { bar: ChartColumn, line: ChartLine, pie: ChartPie, kpi: Hash };
const DEBOUNCE_MS = 350;

interface Props {
  datasetId: number;
  config: WidgetConfig;
  columns: Columns;
  filters: FilterSpec[];
  index: number;
  onChange: (config: WidgetConfig) => void;
  onRemove: () => void;
}

export function WidgetCard({ datasetId, config, columns, filters, index, onChange, onRemove }: Props) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [state, setState] = useState<{ loading: boolean; result: QueryResult | null; error: string | null }>({
    loading: true,
    result: null,
    error: null,
  });
  const first = useRef(true);

  const spec = specFromConfig(config, columns, filters);
  const key = JSON.stringify(spec);

  // Consulta com debounce; uma resposta antiga (de uma configuração anterior) é cancelada, nunca desenhada.
  useEffect(() => {
    const controller = new AbortController();
    const delay = first.current ? 0 : DEBOUNCE_MS;
    first.current = false;
    setState((s) => ({ ...s, loading: true }));

    const timer = window.setTimeout(() => {
      api<QueryResult>(`/datasets/${datasetId}/query`, { method: "POST", body: key }, controller.signal)
        .then((result) => setState({ loading: false, result, error: null }))
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          setState({ loading: false, result: null, error: err instanceof ApiError ? err.message : "Não foi possível consultar os dados." });
        });
    }, delay);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [datasetId, key]);

  const { loading, result, error } = state;
  const isKpi = config.chart === "kpi";
  const isDatetime = typeOf(columns, config.dimension) === "datetime";
  const aggs = allowedAggs(columns, config.metricColumn);
  const title = autoTitle(config, columns);

  const set = (patch: Partial<WidgetConfig>) => onChange({ ...config, ...patch });
  const setMetricColumn = (metricColumn: string) => {
    const allowed = allowedAggs(columns, metricColumn);
    set({ metricColumn, agg: allowed.includes(config.agg) ? config.agg : allowed[0] });
  };

  const id = `w${index}`;
  const meta = result ? [`${formatNumber(result.total_rows_matched)} linha(s) consideradas`, result.truncated ? `só as ${spec.limit} primeiras categorias` : null].filter(Boolean).join(" · ") : "";

  return (
    <Card className={cn("animate-fade-up flex flex-col gap-3 p-4 transition-opacity", loading && "opacity-70")} data-widget>
      <header className="flex items-start justify-between gap-2">
        <h3 className="min-w-0 text-sm font-semibold [overflow-wrap:anywhere]" data-widget-title>
          {title}
        </h3>
        <div className="flex shrink-0 items-center gap-0.5">
          {loading && <Loader2 className="mr-1 size-4 animate-spin text-subtle" aria-label="Carregando" />}
          <button
            type="button"
            onClick={() => setSettingsOpen((o) => !o)}
            aria-expanded={settingsOpen}
            aria-label={`Personalizar: ${title}`}
            title="Personalizar"
            className={cn(
              "grid size-8 place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-foreground",
              settingsOpen && "bg-accent-soft text-accent",
            )}
          >
            <SlidersHorizontal className="size-4" />
          </button>
          <button
            type="button"
            onClick={onRemove}
            aria-label={`Remover: ${title}`}
            title="Remover"
            className="grid size-8 place-items-center rounded-lg text-muted transition-colors hover:bg-danger/10 hover:text-danger"
          >
            <X className="size-4" />
          </button>
        </div>
      </header>

      <div className={cn("relative min-h-0", isKpi ? "py-2" : "h-[260px]")}>
        {error && (
          <p role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}
        {!error && result && isKpi && (
          <div>
            <p data-kpi-value className="text-4xl leading-tight font-semibold tracking-tight tabular-nums [overflow-wrap:anywhere]">
              {formatValue(result.series[0]?.data[0])}
            </p>
            <p className="mt-1 text-sm text-muted">{result.series[0]?.name}</p>
          </div>
        )}
        {!error && result && !isKpi && result.categories.length === 0 && (
          <p className="grid h-full place-items-center text-sm text-muted">Sem dados para este recorte.</p>
        )}
        {!error && result && !isKpi && result.categories.length > 0 && <QueryChart spec={spec} result={result} className="h-full w-full" />}
        {!error && !result && <div className="h-full animate-pulse rounded-lg bg-surface-2" />}
      </div>

      {meta && <p className="text-xs text-subtle">{meta}</p>}

      {settingsOpen && (
        <div className="space-y-3 border-t border-border pt-3">
          <div role="radiogroup" aria-label="Tipo de gráfico" className="grid grid-cols-4 gap-1.5">
            {(Object.keys(CHART_LABELS) as ChartType[]).map((chart) => {
              const Icon = CHART_ICONS[chart];
              const selected = config.chart === chart;
              return (
                <button
                  key={chart}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => set({ chart })}
                  className={cn(
                    "flex flex-col items-center gap-1 rounded-lg border px-2 py-2 text-xs font-medium transition-colors",
                    selected ? "border-accent bg-accent-soft text-foreground" : "border-border text-muted hover:bg-surface-2 hover:text-foreground",
                  )}
                >
                  <Icon className={cn("size-4", selected && "text-accent")} />
                  {CHART_LABELS[chart]}
                </button>
              );
            })}
          </div>

          <div className="grid grid-cols-2 gap-3">
            {!isKpi && (
              <Field label="Eixo X (agrupar por)" htmlFor={`${id}-dim`}>
                <Select id={`${id}-dim`} value={config.dimension} onChange={(e) => set({ dimension: e.target.value })}>
                  {columns.map((c) => (
                    <option key={c.column_name} value={c.column_name}>
                      {c.column_name}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            {!isKpi && isDatetime && (
              <Field label="Agrupar datas por" htmlFor={`${id}-grain`}>
                <Select id={`${id}-grain`} value={config.grain} onChange={(e) => set({ grain: e.target.value as TimeGrain })}>
                  {(Object.keys(GRAIN_LABELS) as TimeGrain[]).map((g) => (
                    <option key={g} value={g}>
                      {GRAIN_LABELS[g]}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            <Field label="Métrica (coluna)" htmlFor={`${id}-metric`}>
              <Select id={`${id}-metric`} value={config.metricColumn} onChange={(e) => setMetricColumn(e.target.value)}>
                {columns.map((c) => (
                  <option key={c.column_name} value={c.column_name}>
                    {c.column_name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Agregação" htmlFor={`${id}-agg`}>
              <Select id={`${id}-agg`} value={config.agg} onChange={(e) => set({ agg: e.target.value as Agg })}>
                {aggs.map((a) => (
                  <option key={a} value={a}>
                    {AGG_LABELS[a]}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </div>
      )}
    </Card>
  );
}
