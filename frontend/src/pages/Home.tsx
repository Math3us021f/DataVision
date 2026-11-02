import {
  Database,
  FileSpreadsheet,
  FileText,
  Files,
  FolderOpen,
  KeyRound,
  MemoryStick,
  Cpu,
  RefreshCw,
  Trash2,
  Upload,
  UserCheck,
  UserPlus,
  UserX,
  Users,
  ChartColumn,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

import { StatusDonut } from "@/components/charts/StatusDonut";
import { UploadsChart } from "@/components/charts/UploadsChart";
import { SmartLink } from "@/components/SmartLink";
import { Stat } from "@/components/Stat";
import { buttonStyles } from "@/components/ui/button";
import { Card, CardHeader, CardSubtitle, CardTitle } from "@/components/ui/card";
import { RadialProgress, toneForUsage } from "@/components/ui/radial-progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { cn, formatBytes, formatNumber, fullDate, relativeTime } from "@/lib/utils";
import type { AuditEntry, Me, Summary, SystemMetrics } from "@/types";

const ACTIONS: Record<string, { icon: LucideIcon; tone: string; text: (e: AuditEntry) => string }> = {
  create_user: { icon: UserPlus, tone: "text-accent", text: (e) => `${who(e)} criou o usuário ${e.target ?? "(excluído)"}` },
  activate_user: { icon: UserCheck, tone: "text-success", text: (e) => `${who(e)} ativou o usuário ${e.target ?? "(excluído)"}` },
  deactivate_user: { icon: UserX, tone: "text-warning", text: (e) => `${who(e)} desativou o usuário ${e.target ?? "(excluído)"}` },
  reset_password: { icon: KeyRound, tone: "text-accent", text: (e) => `${who(e)} redefiniu a senha de ${e.target ?? "(excluído)"}` },
  change_own_password: { icon: KeyRound, tone: "text-muted", text: (e) => `${who(e)} trocou a própria senha` },
  delete_user: { icon: Trash2, tone: "text-danger", text: (e) => `${who(e)} excluiu um usuário (${e.details ?? ""})` },
  force_delete_user_datasets: { icon: Trash2, tone: "text-danger", text: (e) => `${who(e)} apagou datasets de ${e.target ?? "um usuário"}` },
};

const who = (e: AuditEntry): string => e.actor ?? "usuário excluído";

function describe(entry: AuditEntry): { icon: LucideIcon; tone: string; text: string } {
  const known = ACTIONS[entry.action];
  if (known) return { icon: known.icon, tone: known.tone, text: known.text(entry) };
  return { icon: ChartColumn, tone: "text-muted", text: `${who(entry)} ${entry.action}` };
}

function SectionLabel({ children }: { children: ReactNode }) {
  return <h2 className="mb-1.5 text-[11px] font-semibold tracking-[0.12em] text-subtle uppercase short:hidden">{children}</h2>;
}

function ListSkeleton() {
  return (
    <div className="space-y-3 pt-1">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="size-8 rounded-lg" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-2/3" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Home({ me }: { me: Me }) {
  const summary = useApi<Summary>("/dashboard/summary", 30_000);
  const metrics = useApi<SystemMetrics>(me.is_admin ? "/metrics/system" : null, 10_000);

  const data = summary.data;
  const loading = summary.loading && !data;
  const mine = data?.mine;
  const admin = data?.admin;
  const uploads = data?.uploads_by_day ?? [];
  const last7 = uploads.reduce((sum, d) => sum + d.count, 0);
  const today = uploads.length ? uploads[uploads.length - 1].count : 0;
  const pending = mine ? Math.max(0, mine.datasets - mine.profiled) : 0;
  const profiledPct = mine && mine.datasets > 0 ? (mine.profiled / mine.datasets) * 100 : 0;

  const todayLabel = new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });

  if (summary.error && !data) {
    return (
      <main className="p-6">
        <Card className="mx-auto mt-16 max-w-md p-8 text-center" role="alert">
          <p className="font-semibold">Não foi possível carregar o painel</p>
          <p className="mt-1 text-sm text-muted">{summary.error}</p>
          <button type="button" onClick={summary.reload} className={cn(buttonStyles({ variant: "primary" }), "mt-5")}>
            <RefreshCw className="size-4" /> Tentar de novo
          </button>
        </Card>
      </main>
    );
  }

  return (
    <main className="flex flex-col gap-4 p-4 md:p-6 fit:h-screen fit:overflow-hidden fit:px-7 fit:py-5 short:gap-3 short:py-3">
      <header className="flex shrink-0 flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-muted first-letter:uppercase short:hidden">{todayLabel}</p>
          <h1 className="text-2xl font-semibold tracking-tight">Olá, {me.username}</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              summary.reload();
              metrics.reload();
            }}
            aria-label="Atualizar dados"
            title="Atualizar dados"
            className={buttonStyles({ variant: "secondary", size: "icon" })}
          >
            <RefreshCw className={cn("size-4", summary.loading && "animate-spin")} />
          </button>
          <SmartLink href="/app/datasets" className={buttonStyles({ variant: "primary" })}>
            <Upload className="size-4" /> Enviar dataset
          </SmartLink>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 short:gap-3 fit:min-h-0 fit:flex-1 fit:grid-rows-[auto_minmax(0,1.15fr)_minmax(0,1fr)]">
        {/* Indicadores */}
        <div className="grid grid-cols-1 gap-4 short:gap-3 2xl:grid-cols-12">
          <section className={cn("animate-fade-up", me.is_admin ? "2xl:col-span-5" : "2xl:col-span-12")}>
            <SectionLabel>Meus dados</SectionLabel>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Stat
                id="stat-datasets"
                label="Datasets enviados"
                icon={Files}
                href="/app/datasets"
                loading={loading}
                value={mine?.datasets ?? null}
                format={(n) => formatNumber(Math.round(n))}
                detail={today > 0 ? `+${today} hoje` : `${last7} em 7 dias`}
              />
              <Stat
                id="stat-storage"
                label="Espaço usado"
                icon={Database}
                loading={loading}
                value={mine?.storage_bytes ?? null}
                format={(n) => formatBytes(n)}
                detail={mine && mine.datasets > 0 ? `≈ ${formatBytes(mine.storage_bytes / mine.datasets)} por arquivo` : "nenhum arquivo ainda"}
              />
              <Stat
                id="stat-profiled"
                label="Perfilados"
                icon={ChartColumn}
                loading={loading}
                value={mine?.profiled ?? null}
                format={(n) => formatNumber(Math.round(n))}
                detail={mine ? `de ${formatNumber(mine.datasets)}` : ""}
                accessory={<RadialProgress value={profiledPct} />}
              />
            </div>
          </section>

          {me.is_admin && (
            <section className="animate-fade-up 2xl:col-span-7" style={{ animationDelay: "60ms" }}>
              <SectionLabel>Sistema</SectionLabel>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-4">
                <Stat
                  id="stat-users"
                  label="Usuários ativos"
                  icon={Users}
                  href="/admin/users"
                  loading={loading}
                  value={admin?.users.active ?? null}
                  format={(n) => formatNumber(Math.round(n))}
                  detail={admin ? `${formatNumber(admin.users.inactive)} inativos · ${formatNumber(admin.users.total)} total` : ""}
                />
                <Stat
                  id="stat-all-datasets"
                  label="Datasets no sistema"
                  icon={FolderOpen}
                  loading={loading}
                  value={admin?.datasets_total ?? null}
                  format={(n) => formatNumber(Math.round(n))}
                  detail="de todos os usuários"
                />
                <Stat
                  id="stat-cpu"
                  label="CPU"
                  icon={Cpu}
                  href="/admin/metrics"
                  loading={metrics.loading && !metrics.data}
                  value={metrics.data?.cpu_percent ?? null}
                  format={(n) => `${n.toFixed(1)}%`}
                  detail="uso agora"
                  accessory={metrics.data && <RadialProgress value={metrics.data.cpu_percent} tone={toneForUsage(metrics.data.cpu_percent)} />}
                />
                <Stat
                  id="stat-memory"
                  label="Memória"
                  icon={MemoryStick}
                  href="/admin/metrics"
                  loading={metrics.loading && !metrics.data}
                  value={metrics.data?.memory.percent ?? null}
                  format={(n) => `${n.toFixed(1)}%`}
                  detail={metrics.data ? `de ${formatBytes(metrics.data.memory.total_bytes)}` : ""}
                  accessory={
                    metrics.data && <RadialProgress value={metrics.data.memory.percent} tone={toneForUsage(metrics.data.memory.percent)} />
                  }
                />
              </div>
            </section>
          )}
        </div>

        {/* Gráficos */}
        <div className="grid grid-cols-1 gap-4 short:gap-3 fit:min-h-0 lg:grid-cols-12">
          <Card className="animate-fade-up flex min-h-[260px] flex-col p-4 short:p-3 fit:min-h-0 lg:col-span-5" style={{ animationDelay: "120ms" }}>
            <CardHeader>
              <div>
                <CardTitle>Uploads por dia</CardTitle>
                <CardSubtitle id="uploads-sub" className="short:hidden">{loading ? " " : `${last7} ${last7 === 1 ? "dataset enviado" : "datasets enviados"} nos últimos 7 dias`}</CardSubtitle>
              </div>
              <span className="rounded-full bg-surface-2 px-2.5 py-1 text-[11px] font-medium text-muted short:hidden">7 dias</span>
            </CardHeader>
            {loading ? <Skeleton className="mt-3 min-h-0 flex-1" /> : <UploadsChart data={uploads} className="mt-1 min-h-0 flex-1" />}
          </Card>

          <Card className="animate-fade-up flex min-h-[260px] flex-col p-4 short:p-3 fit:min-h-0 lg:col-span-7" style={{ animationDelay: "180ms" }}>
            <CardHeader>
              <div>
                <CardTitle>Status dos datasets</CardTitle>
                <CardSubtitle className="short:hidden">perfilados vs. pendentes</CardSubtitle>
              </div>
              {pending > 0 && (
                <SmartLink href="/app/datasets" className={buttonStyles({ variant: "secondary", size: "sm" })}>
                  Perfilar pendentes
                </SmartLink>
              )}
            </CardHeader>
            {loading || !mine ? (
              <Skeleton className="mt-3 min-h-0 flex-1" />
            ) : (
              <div className="mt-1 flex min-h-0 flex-1 flex-wrap items-center justify-center gap-x-14 gap-y-4">
                <StatusDonut profiled={mine.profiled} total={mine.datasets} className="aspect-square h-full max-h-[190px] min-h-[84px]" />
                <dl className="min-w-[200px] space-y-3 text-sm">
                  <div className="flex items-center gap-3">
                    <span className="size-2.5 rounded-full bg-accent" />
                    <dt className="text-muted">Perfilados</dt>
                    <dd id="legend-profiled" className="ml-auto font-semibold tabular-nums">{formatNumber(mine.profiled)}</dd>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="size-2.5 rounded-full bg-surface-2 ring-1 ring-border" />
                    <dt className="text-muted">Pendentes</dt>
                    <dd id="legend-pending" className="ml-auto font-semibold tabular-nums">{formatNumber(pending)}</dd>
                  </div>
                </dl>
              </div>
            )}
          </Card>
        </div>

        {/* Listas */}
        <div className="grid grid-cols-1 gap-4 short:gap-3 fit:min-h-0 lg:grid-cols-12">
          <Card
            className={cn("animate-fade-up flex min-h-[220px] flex-col p-4 fit:min-h-0", me.is_admin ? "lg:col-span-5" : "lg:col-span-12")}
            style={{ animationDelay: "240ms" }}
          >
            <CardHeader>
              <CardTitle>Últimos envios</CardTitle>
              <SmartLink href="/app/datasets" className="text-xs font-medium text-muted underline-offset-4 hover:text-accent hover:underline">
                Ver todos
              </SmartLink>
            </CardHeader>
            <ul id="recent-datasets" className="scroll-thin -mx-1 mt-2 min-h-0 flex-1 space-y-0.5 overflow-y-auto px-1">
              {loading && <ListSkeleton />}
              {data?.recent_datasets.map((d) => {
                const Icon = d.format === ".xlsx" ? FileSpreadsheet : FileText;
                return (
                  <li key={d.id} className="flex items-center gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-surface-2">
                    <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent">
                      <Icon className="size-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{d.original_name}</p>
                      <p className="text-xs text-subtle">
                        {d.format.replace(".", "").toUpperCase()} · {formatBytes(d.size_bytes)}
                      </p>
                    </div>
                    <time dateTime={d.created_at} title={fullDate(d.created_at)} className="shrink-0 text-xs text-muted">
                      {relativeTime(d.created_at)}
                    </time>
                  </li>
                );
              })}
              {data && data.recent_datasets.length === 0 && (
                <li className="py-6 text-center text-sm text-muted">Nenhum arquivo enviado ainda.</li>
              )}
            </ul>
          </Card>

          {me.is_admin && (
            <Card className="animate-fade-up flex min-h-[220px] flex-col p-4 fit:min-h-0 lg:col-span-7" style={{ animationDelay: "300ms" }}>
              <CardHeader>
                <CardTitle>Atividade administrativa</CardTitle>
                <a href="/admin/audit" className="text-xs font-medium text-muted underline-offset-4 hover:text-accent hover:underline">
                  Ver tudo
                </a>
              </CardHeader>
              <ul id="recent-audit" className="scroll-thin -mx-1 mt-2 min-h-0 flex-1 space-y-0.5 overflow-y-auto px-1">
                {loading && <ListSkeleton />}
                {admin?.recent_audit.map((entry, i) => {
                  const { icon: Icon, tone, text } = describe(entry);
                  return (
                    <li key={`${entry.created_at}-${i}`} className="flex items-center gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-surface-2">
                      <span className={cn("grid size-8 shrink-0 place-items-center rounded-lg bg-surface-2", tone)}>
                        <Icon className="size-4" />
                      </span>
                      <p className="min-w-0 flex-1 truncate text-sm">{text}</p>
                      <time dateTime={entry.created_at} title={fullDate(entry.created_at)} className="shrink-0 text-xs text-muted">
                        {relativeTime(entry.created_at)}
                      </time>
                    </li>
                  );
                })}
                {admin && admin.recent_audit.length === 0 && (
                  <li className="py-6 text-center text-sm text-muted">Nenhuma atividade registrada.</li>
                )}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </main>
  );
}
