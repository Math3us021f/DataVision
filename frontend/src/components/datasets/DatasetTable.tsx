import { ChartColumn, ChevronLeft, ChevronRight, FileSpreadsheet, FileText, LayoutDashboard, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { Card, CardHeader, CardSubtitle, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatBytes, fullDate, relativeTime } from "@/lib/utils";
import type { Dataset } from "@/types";

const PAGE_SIZE = 8;

export function DatasetTable({
  datasets,
  loading,
  onProfile,
  onDelete,
}: {
  datasets: Dataset[] | null;
  loading: boolean;
  onProfile: (d: Dataset) => void;
  onDelete: (d: Dataset) => void;
}) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (datasets ?? []).filter((d) => d.original_name.toLowerCase().includes(term));
  }, [datasets, search]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const visible = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);
  const total = datasets?.length ?? 0;

  return (
    <Card className="flex min-h-0 flex-col p-4">
      <CardHeader className="items-center">
        <div>
          <CardTitle>Meus datasets</CardTitle>
          <CardSubtitle>{loading && !datasets ? " " : `${total} ${total === 1 ? "arquivo" : "arquivos"}`}</CardSubtitle>
        </div>
        <label className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle" />
          <input
            type="search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Buscar por nome"
            aria-label="Buscar por nome"
            className="h-9 w-full rounded-lg border border-border bg-background pr-3 pl-9 text-sm placeholder:text-subtle focus-visible:outline-2 focus-visible:outline-accent"
          />
        </label>
      </CardHeader>

      <div className="scroll-thin -mx-1 mt-3 overflow-x-auto px-1">
        <table id="datasets-table" className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="text-left text-[11px] font-semibold tracking-[0.08em] text-subtle uppercase">
              <th className="py-2 pr-3 font-semibold">Nome</th>
              <th className="px-3 py-2 font-semibold">Tamanho</th>
              <th className="px-3 py-2 font-semibold">Enviado</th>
              <th className="px-3 py-2 font-semibold">Perfil</th>
              <th className="py-2 pl-3" />
            </tr>
          </thead>
          <tbody>
            {loading && !datasets &&
              Array.from({ length: 4 }, (_, i) => (
                <tr key={i} className="border-t border-border">
                  <td colSpan={5} className="py-3">
                    <Skeleton className="h-8 w-full" />
                  </td>
                </tr>
              ))}
            {visible.map((d) => {
              const Icon = d.format === ".xlsx" ? FileSpreadsheet : FileText;
              return (
                <tr key={d.id} data-dataset-id={d.id} className="group border-t border-border transition-colors hover:bg-surface-2/60">
                  <td className="max-w-[320px] py-2.5 pr-3">
                    <div className="flex items-center gap-3">
                      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent">
                        <Icon className="size-4" />
                      </span>
                      <div className="min-w-0">
                        <p className="truncate font-medium" title={d.original_name}>
                          {d.original_name}
                        </p>
                        <p className="text-xs text-subtle">{d.format.replace(".", "").toUpperCase()}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap text-muted tabular-nums">{formatBytes(d.size_bytes)}</td>
                  <td className="px-3 py-2.5 whitespace-nowrap text-muted">
                    {d.created_at ? <time title={fullDate(d.created_at)}>{relativeTime(d.created_at)}</time> : "—"}
                  </td>
                  <td className="px-3 py-2.5">
                    {d.profiled ? <Badge tone="success">Perfilado</Badge> : <Badge>Pendente</Badge>}
                  </td>
                  <td className="py-2.5 pl-3">
                    <div className="flex items-center justify-end gap-1.5">
                      <button type="button" onClick={() => onProfile(d)} className={buttonStyles({ variant: "secondary", size: "sm" })}>
                        <ChartColumn className="size-3.5" /> Perfil
                      </button>
                      <a
                        href={`/meus-datasets/${d.id}/dashboard`}
                        className={buttonStyles({ variant: "secondary", size: "sm" })}
                      >
                        <LayoutDashboard className="size-3.5" /> Dashboard
                      </a>
                      <button
                        type="button"
                        onClick={() => onDelete(d)}
                        aria-label={`Excluir ${d.original_name}`}
                        title="Excluir"
                        className="grid size-8 place-items-center rounded-lg text-muted transition-colors hover:bg-danger/10 hover:text-danger"
                      >
                        <Trash2 className="size-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {datasets && filtered.length === 0 && (
          <div className="py-10 text-center" role="status">
            <p className="text-sm font-semibold">{total === 0 ? "Nenhum dataset enviado" : "Nenhum resultado"}</p>
            <p className="mt-1 text-sm text-muted">
              {total === 0 ? "Envie um arquivo CSV ou Excel acima para começar." : "Tente outro termo de busca."}
            </p>
          </div>
        )}
      </div>

      {filtered.length > PAGE_SIZE && (
        <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-xs text-muted">
          <span>
            Mostrando {(current - 1) * PAGE_SIZE + 1}–{Math.min(current * PAGE_SIZE, filtered.length)} de {filtered.length}
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Página anterior"
              disabled={current <= 1}
              onClick={() => setPage(current - 1)}
              className={cn(buttonStyles({ variant: "ghost", size: "icon" }), "size-8")}
            >
              <ChevronLeft className="size-4" />
            </button>
            <span className="px-1 tabular-nums">
              {current} / {pages}
            </span>
            <button
              type="button"
              aria-label="Próxima página"
              disabled={current >= pages}
              onClick={() => setPage(current + 1)}
              className={cn(buttonStyles({ variant: "ghost", size: "icon" }), "size-8")}
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
