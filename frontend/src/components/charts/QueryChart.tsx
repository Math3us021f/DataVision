import { useMemo } from "react";

import { EChart, echarts, useChartColors, withAlpha, type EChartsCoreOption } from "@/components/charts/EChart";
import type { QueryResult, QuerySpec } from "@/types";

const numberFormat = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
const compactFormat = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });

export const formatValue = (value: number | null | undefined): string =>
  value === null || value === undefined ? "—" : numberFormat.format(value);

/**
 * Resposta da API ({categories, series}) → gráfico. Categorias e nomes vêm dos dados do usuário:
 * entram só como dados do ECharts, e o tooltip usa `valueFormatter` (nunca um `formatter` com HTML).
 */
export function QueryChart({ spec, result, className }: { spec: QuerySpec; result: QueryResult; className?: string }) {
  const c = useChartColors();

  const option = useMemo<EChartsCoreOption>(() => {
    const palette = [c.accent, c.success, "#d9a441", "#5a8fd9", "#e2584a", "#9b7fd1"];
    const tooltip = {
      backgroundColor: c.surface,
      borderColor: c.border,
      textStyle: { color: c.foreground, fontSize: 12 },
      valueFormatter: formatValue,
    };
    const base = { color: palette, animationDuration: 500, textStyle: { color: c.muted } };

    if (spec.chart === "pie") {
      return {
        ...base,
        tooltip: { ...tooltip, trigger: "item" },
        legend: { type: "scroll", bottom: 0, textStyle: { color: c.muted } },
        series: [
          {
            type: "pie",
            radius: ["42%", "68%"],
            center: ["50%", "44%"],
            padAngle: 2,
            itemStyle: { borderColor: c.surface, borderWidth: 2, borderRadius: 6 },
            label: { color: c.muted },
            data: result.categories.map((name, i) => ({ name, value: result.series[0].data[i] })),
          },
        ],
      };
    }

    const multi = result.series.length > 1;
    const isLine = spec.chart === "line";
    return {
      ...base,
      tooltip: { ...tooltip, trigger: "axis" },
      legend: multi ? { top: 0, textStyle: { color: c.muted } } : undefined,
      grid: { left: 4, right: 14, top: multi ? 34 : 14, bottom: 4, containLabel: true },
      xAxis: {
        type: "category",
        data: result.categories,
        boundaryGap: !isLine,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: c.border } },
        axisLabel: { color: c.muted, hideOverlap: true },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: c.muted, formatter: (v: number) => compactFormat.format(v) },
        splitLine: { lineStyle: { color: c.border, type: "dashed" } },
      },
      series: result.series.map((s, i) => {
        const color = palette[i % palette.length];
        return isLine
          ? {
              name: s.name,
              type: "line",
              smooth: 0.3,
              showSymbol: result.categories.length <= 40,
              data: s.data,
              lineStyle: { width: 3, color },
              itemStyle: { color },
              areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: withAlpha(color, multi ? 0.12 : 0.3) },
                  { offset: 1, color: withAlpha(color, 0) },
                ]),
              },
            }
          : { name: s.name, type: "bar", data: s.data, barMaxWidth: 42, itemStyle: { color, borderRadius: [5, 5, 0, 0] } };
      }),
    };
  }, [spec.chart, result, c]);

  return <EChart option={option} className={className} />;
}
