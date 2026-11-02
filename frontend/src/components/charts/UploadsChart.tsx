import { useMemo } from "react";

import { EChart, echarts, useChartColors, withAlpha, type EChartsCoreOption } from "@/components/charts/EChart";
import { weekdayLabel } from "@/lib/utils";
import type { UploadDay } from "@/types";

function dayLabel(day: string): string {
  const [, month, date] = day.split("-");
  return `${weekdayLabel(day)}, ${date}/${month}`;
}

export function UploadsChart({ data, className }: { data: UploadDay[]; className?: string }) {
  const c = useChartColors();

  const option = useMemo<EChartsCoreOption>(
    () => ({
      animationDuration: 700,
      grid: { left: 4, right: 16, top: 20, bottom: 4, containLabel: true },
      tooltip: {
        trigger: "axis",
        backgroundColor: c.surface,
        borderColor: c.border,
        textStyle: { color: c.foreground, fontSize: 12 },
        valueFormatter: (value: number) => `${value} envio(s)`, // só números: nada de HTML com dados
        axisPointer: { type: "line", lineStyle: { color: c.border } },
      },
      xAxis: {
        type: "category",
        data: data.map((d) => dayLabel(d.day)),
        boundaryGap: false,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: c.muted, formatter: (v: string) => v.split(",")[0] },
      },
      yAxis: {
        type: "value",
        minInterval: 1,
        splitNumber: 3,
        axisLabel: { color: c.muted },
        splitLine: { lineStyle: { color: c.border, type: "dashed" } },
      },
      series: [
        {
          type: "line",
          smooth: 0.35,
          symbol: "circle",
          symbolSize: 8,
          data: data.map((d) => d.count),
          lineStyle: { width: 3, color: c.accent },
          itemStyle: { color: c.accent, borderColor: c.surface, borderWidth: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: withAlpha(c.accent, 0.35) },
              { offset: 1, color: withAlpha(c.accent, 0) },
            ]),
          },
        },
      ],
    }),
    [data, c],
  );

  return <EChart option={option} className={className} />;
}
