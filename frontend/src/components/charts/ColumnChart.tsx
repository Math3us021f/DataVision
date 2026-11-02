import { useMemo } from "react";

import { EChart, useChartColors, type EChartsCoreOption } from "@/components/charts/EChart";
import type { ColumnProfile } from "@/types";

const round = (n: number) => (Number.isInteger(n) ? n : Math.round(n * 100) / 100);

/** Histograma (coluna numérica) ou valores mais frequentes (coluna de texto). Retorna null se não houver o que mostrar. */
export function ColumnChart({ column, className }: { column: ColumnProfile; className?: string }) {
  const c = useChartColors();

  const option = useMemo<EChartsCoreOption | null>(() => {
    const common = {
      animationDuration: 500,
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: c.surface,
        borderColor: c.border,
        textStyle: { color: c.foreground, fontSize: 12 },
        valueFormatter: (v: number) => `${v} linha(s)`, // só números: nada de HTML com dados do arquivo
      },
    };
    const bar = { type: "bar", itemStyle: { color: c.accent, borderRadius: 4 }, barMaxWidth: 28 };

    if (column.histogram) {
      const { bin_edges: edges, counts } = column.histogram;
      return {
        ...common,
        grid: { left: 4, right: 8, top: 8, bottom: 4, containLabel: true },
        xAxis: {
          type: "category",
          data: counts.map((_, i) => `${round(edges[i])}–${round(edges[i + 1])}`),
          axisTick: { show: false },
          axisLine: { lineStyle: { color: c.border } },
          axisLabel: { color: c.muted, fontSize: 10, hideOverlap: true },
        },
        yAxis: { type: "value", minInterval: 1, splitNumber: 3, axisLabel: { color: c.muted, fontSize: 10 }, splitLine: { lineStyle: { color: c.border, type: "dashed" } } },
        series: [{ ...bar, data: counts }],
      };
    }

    if (column.top_values && column.top_values.length > 0) {
      return {
        ...common,
        grid: { left: 4, right: 24, top: 4, bottom: 4, containLabel: true },
        xAxis: { type: "value", minInterval: 1, splitNumber: 3, axisLabel: { color: c.muted, fontSize: 10 }, splitLine: { lineStyle: { color: c.border, type: "dashed" } } },
        yAxis: {
          type: "category",
          inverse: true,
          data: column.top_values.map((t) => t.value),
          axisTick: { show: false },
          axisLine: { show: false },
          axisLabel: { color: c.muted, fontSize: 11, width: 110, overflow: "truncate" },
        },
        series: [{ ...bar, data: column.top_values.map((t) => t.count) }],
      };
    }
    return null;
  }, [column, c]);

  if (!option) return null;
  return <EChart option={option} className={className} />;
}
