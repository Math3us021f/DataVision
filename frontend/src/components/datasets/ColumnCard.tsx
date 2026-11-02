import { ColumnChart } from "@/components/charts/ColumnChart";
import { Badge } from "@/components/ui/badge";
import { cn, formatNumber } from "@/lib/utils";
import type { ColumnProfile } from "@/types";

const TYPE_LABELS: Record<string, string> = {
  integer: "Inteiro",
  float: "Decimal",
  text: "Texto",
  boolean: "Booleano",
  datetime: "Data/hora",
};

const num = (n: number) => (Number.isInteger(n) ? formatNumber(n) : n.toLocaleString("pt-BR", { maximumFractionDigits: 2 }));

function Meter({ label, percent, tone }: { label: string; percent: number; tone: "accent" | "warning" | "danger" }) {
  const fill = { accent: "bg-accent", warning: "bg-warning", danger: "bg-danger" }[tone];
  return (
    <div>
      <p className="text-xs text-muted">{label}</p>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-2">
        <div className={cn("h-full rounded-full", fill)} style={{ width: `${Math.min(100, percent)}%` }} />
      </div>
    </div>
  );
}

export function ColumnCard({ column, totalRows }: { column: ColumnProfile; totalRows: number }) {
  const nullPct = totalRows ? (column.null_count / totalRows) * 100 : 0;
  const distinctPct = totalRows ? (column.distinct_count / totalRows) * 100 : 0;
  const hasChart = column.histogram !== null || (column.top_values?.length ?? 0) > 0;

  return (
    <article className="rounded-xl border border-border bg-background/40 p-4">
      <div className="flex items-start justify-between gap-2">
        <h3 className="min-w-0 truncate text-sm font-semibold" title={column.column_name}>
          {column.column_name}
        </h3>
        <Badge tone="accent">{TYPE_LABELS[column.inferred_type] ?? column.inferred_type}</Badge>
      </div>

      <div className="mt-3 space-y-2.5">
        <Meter
          label={`Ausentes: ${formatNumber(column.null_count)} (${nullPct.toFixed(1)}%)`}
          percent={nullPct}
          tone={nullPct >= 50 ? "danger" : nullPct >= 15 ? "warning" : "accent"}
        />
        <Meter label={`Valores distintos: ${formatNumber(column.distinct_count)} (${distinctPct.toFixed(1)}%)`} percent={distinctPct} tone="accent" />
      </div>

      {column.min_value !== null && column.max_value !== null && column.mean_value !== null && column.median_value !== null && (
        <dl className="mt-3 grid grid-cols-4 gap-2">
          {(
            [
              ["Mín.", column.min_value],
              ["Máx.", column.max_value],
              ["Média", column.mean_value],
              ["Mediana", column.median_value],
            ] as const
          ).map(([label, value]) => (
            <div key={label} className="rounded-lg bg-surface-2 px-2 py-1.5">
              <dt className="text-[10px] font-medium tracking-wide text-subtle uppercase">{label}</dt>
              <dd className="truncate text-sm font-semibold tabular-nums" title={String(value)}>
                {num(value)}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {hasChart && (
        <div className="mt-3">
          <p className="mb-1 text-[11px] font-medium text-subtle">
            {column.histogram ? "Distribuição" : "Valores mais frequentes"}
          </p>
          {/* Altura fixa: o ECharts mede o elemento e, sem isso, não sabe o tamanho do gráfico. */}
          <ColumnChart column={column} className="h-40 w-full" />
        </div>
      )}
    </article>
  );
}
