import { LineChart, PieChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import type { EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef } from "react";

import { useTheme } from "@/hooks/useTheme";

// Só o que a Home usa entra no pacote (em vez do ECharts inteiro).
echarts.use([LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

export { echarts };
export type { EChartsCoreOption };

/** Uma instância do ECharts por container; redimensiona sozinha e libera a memória ao sair. */
export function EChart({ option, className }: { option: EChartsCoreOption; className?: string }) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!container.current) return;
    const instance = echarts.init(container.current);
    chart.current = instance;
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      instance.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, { notMerge: true });
  }, [option]);

  return <div ref={container} className={className} />;
}

/** As cores dos gráficos vêm das variáveis CSS do tema; recalcula quando o tema muda. */
export function useChartColors() {
  const { theme } = useTheme();
  return useMemo(() => {
    const style = getComputedStyle(document.documentElement);
    const read = (name: string) => style.getPropertyValue(name).trim();
    return {
      accent: read("--accent"),
      success: read("--success"),
      muted: read("--muted"),
      border: read("--border"),
      surface: read("--surface"),
      surface2: read("--surface-2"),
      foreground: read("--foreground"),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `theme` é o gatilho para reler as variáveis
  }, [theme]);
}

export function withAlpha(hex: string, alpha: number): string {
  const value = hex.replace("#", "");
  const n = parseInt(value.length === 3 ? value.replace(/./g, "$&$&") : value, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}
