import { Cpu, HardDrive, Info, MemoryStick, Network, type LucideIcon } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

import { AdminPage, ErrorPanel } from "@/components/admin/AdminPage";
import { Card, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { cn, formatBytes } from "@/lib/utils";
import type { FullMetrics } from "@/types";

const REFRESH_MS = 5000;

function Meter({ id, label, icon: Icon, percent, detail }: { id: string; label: string; icon: LucideIcon; percent: number | null; detail?: ReactNode }) {
  const tone = percent === null ? "bg-accent" : percent >= 90 ? "bg-danger" : percent >= 70 ? "bg-warning" : "bg-accent";
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <span className="grid size-8 place-items-center rounded-lg bg-accent-soft text-accent">
          <Icon className="size-4" />
        </span>
        {label}
      </div>
      {percent === null ? (
        <Skeleton className="mt-3 h-9 w-24" />
      ) : (
        <p id={`${id}-value`} className="mt-3 text-3xl font-semibold tracking-tight tabular-nums">
          {percent.toFixed(1)}%
        </p>
      )}
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(percent ?? 0)}>
        <div className={cn("h-full rounded-full transition-[width] duration-500", tone)} style={{ width: `${Math.min(percent ?? 0, 100)}%` }} />
      </div>
      <p id={`${id}-detail`} className="mt-2 min-h-4 text-xs text-muted">
        {detail}
      </p>
    </Card>
  );
}

export default function Metrics() {
  const metrics = useApi<FullMetrics>("/metrics/system", REFRESH_MS);
  const m = metrics.data;

  const peak = useRef(0);
  const updatedAt = useRef<Date | null>(null);
  useEffect(() => {
    if (m) {
      peak.current = Math.max(peak.current, m.cpu_percent);
      updatedAt.current = new Date();
    }
  }, [m]);

  return (
    <AdminPage
      title="Métricas do sistema"
      subtitle="Atualização automática a cada 5 segundos."
      actions={
        <span id="metrics-updated" className="inline-flex items-center gap-2 text-xs text-muted">
          <span className="size-2 animate-pulse rounded-full bg-success" aria-hidden="true" />
          {m ? `Atualizado às ${(updatedAt.current ?? new Date()).toLocaleTimeString("pt-BR")}` : "Carregando..."}
        </span>
      }
    >
      {m && (
        <div className="flex items-start gap-3 rounded-card border border-border bg-surface-2/60 p-4 text-sm text-muted">
          <Info className="mt-0.5 size-4 shrink-0 text-accent" />
          <p id="metrics-scope">{m.aviso_escopo}</p>
        </div>
      )}
      {metrics.error && !m && <ErrorPanel title="Não foi possível carregar as métricas" message={metrics.error} />}
      {metrics.error && m && (
        <div role="alert" className="rounded-card border border-danger/40 bg-danger/10 p-3 text-sm">
          {metrics.error}. Mostrando a última leitura.
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Meter id="cpu" label="CPU" icon={Cpu} percent={m?.cpu_percent ?? null} detail={m ? `pico de ${Math.max(peak.current, m.cpu_percent).toFixed(1)}% nesta sessão` : ""} />
        <Meter id="memory" label="Memória" icon={MemoryStick} percent={m?.memory.percent ?? null} detail={m ? `${formatBytes(m.memory.used_bytes)} de ${formatBytes(m.memory.total_bytes)}` : ""} />
        <Meter id="disk" label="Disco" icon={HardDrive} percent={m?.disk.percent ?? null} detail={m ? `${formatBytes(m.disk.used_bytes)} de ${formatBytes(m.disk.total_bytes)}` : ""} />
        <Card className="p-4">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <span className="grid size-8 place-items-center rounded-lg bg-accent-soft text-accent">
              <Network className="size-4" />
            </span>
            <CardTitle>Rede</CardTitle>
          </div>
          <dl className="mt-3 space-y-1.5 text-sm">
            <div className="flex justify-between gap-2">
              <dt className="text-muted">Enviado</dt>
              <dd id="net-sent" className="font-semibold tabular-nums">{m ? formatBytes(m.network.bytes_sent) : "—"}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted">Recebido</dt>
              <dd id="net-recv" className="font-semibold tabular-nums">{m ? formatBytes(m.network.bytes_recv) : "—"}</dd>
            </div>
          </dl>
          <p className="mt-3 text-xs text-muted">Total acumulado desde que o ambiente subiu.</p>
        </Card>
      </div>
    </AdminPage>
  );
}
