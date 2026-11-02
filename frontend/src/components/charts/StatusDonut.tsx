import { useMemo } from "react";

import { EChart, useChartColors, type EChartsCoreOption } from "@/components/charts/EChart";

export function StatusDonut({ profiled, total, className }: { profiled: number; total: number; className?: string }) {
  const c = useChartColors();
  const pending = Math.max(0, total - profiled);
  const pct = total > 0 ? Math.round((profiled / total) * 100) : 0;

  const option = useMemo<EChartsCoreOption>(
    () => ({
      animationDuration: 700,
      tooltip: {
        trigger: "item",
        backgroundColor: c.surface,
        borderColor: c.border,
        textStyle: { color: c.foreground, fontSize: 12 },
        valueFormatter: (value: number) => `${value} dataset(s)`,
      },
      series: [
        {
          type: "pie",
          radius: ["68%", "88%"],
          center: ["50%", "50%"],
          padAngle: 2,
          itemStyle: { borderRadius: 8 },
          label: { show: false },
          emphasis: { scale: false },
          // Sem nenhum dataset, mostra o anel vazio em vez de nada.
          data:
            total === 0
              ? [{ name: "Sem datasets", value: 1, itemStyle: { color: c.surface2 } }]
              : [
                  { name: "Perfilados", value: profiled, itemStyle: { color: c.accent } },
                  { name: "Pendentes", value: pending, itemStyle: { color: c.surface2 } },
                ],
        },
      ],
    }),
    [c, profiled, pending, total],
  );

  return (
    <div className={`relative ${className ?? ""}`}>
      <EChart option={option} className="absolute inset-0" />
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold tabular-nums tracking-tight">{pct}%</span>
        <span className="text-[11px] text-muted">perfilados</span>
      </div>
    </div>
  );
}
