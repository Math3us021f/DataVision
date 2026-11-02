import { ChartColumn, Database, Files } from "lucide-react";
import { useCallback, useState } from "react";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DatasetTable } from "@/components/datasets/DatasetTable";
import { ProfileDrawer } from "@/components/datasets/ProfileDrawer";
import { UploadZone } from "@/components/datasets/UploadZone";
import { Stat } from "@/components/Stat";
import { RadialProgress } from "@/components/ui/radial-progress";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { formatBytes, formatNumber } from "@/lib/utils";
import type { Dataset, Summary } from "@/types";

export default function Datasets() {
  const toast = useToast();
  const list = useApi<Dataset[]>("/datasets");
  const summary = useApi<Summary>("/dashboard/summary");

  const [profiling, setProfiling] = useState<Dataset | null>(null);
  const [deleting, setDeleting] = useState<Dataset | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    list.reload();
    summary.reload();
  }, [list, summary]);

  async function confirmDelete() {
    if (!deleting) return;
    setBusy(true);
    try {
      await api(`/datasets/${deleting.id}`, { method: "DELETE" });
      toast(`"${deleting.original_name}" excluído.`);
      setDeleting(null);
      refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Erro ao excluir", "error");
    } finally {
      setBusy(false);
    }
  }

  const mine = summary.data?.mine;
  const loading = summary.loading && !summary.data;
  const profiledPct = mine && mine.datasets > 0 ? (mine.profiled / mine.datasets) * 100 : 0;

  return (
    <main className="flex flex-col gap-4 p-4 md:p-6 lg:px-7">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Datasets</h1>
        <p className="mt-0.5 text-sm text-muted">Envie arquivos CSV ou Excel (até 10 MB) para perfilar e montar dashboards.</p>
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Stat id="summary-total" label="Total enviados" icon={Files} loading={loading} value={mine?.datasets ?? null} format={(n) => formatNumber(Math.round(n))} />
        <Stat
          id="summary-profiled"
          label="Perfilados"
          icon={ChartColumn}
          loading={loading}
          value={mine?.profiled ?? null}
          format={(n) => formatNumber(Math.round(n))}
          detail={mine ? `de ${formatNumber(mine.datasets)}` : ""}
          accessory={<RadialProgress value={profiledPct} />}
        />
        <Stat id="summary-storage" label="Espaço usado" icon={Database} loading={loading} value={mine?.storage_bytes ?? null} format={(n) => formatBytes(n)} />
      </div>

      <UploadZone onUploaded={refresh} />

      {list.error && !list.data ? (
        <div role="alert" className="rounded-card border border-danger/40 bg-danger/10 p-6 text-center text-sm">
          <p className="font-semibold">Não foi possível carregar os datasets</p>
          <p className="mt-1 text-muted">{list.error}</p>
        </div>
      ) : (
        <DatasetTable datasets={list.data} loading={list.loading} onProfile={setProfiling} onDelete={setDeleting} />
      )}

      <ProfileDrawer dataset={profiling} onClose={() => setProfiling(null)} onProfiled={refresh} />

      <ConfirmDialog
        open={deleting !== null}
        title="Excluir dataset?"
        confirmLabel="Excluir"
        danger
        busy={busy}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      >
        “{deleting?.original_name}” e seu perfilamento serão apagados, junto com o arquivo armazenado. Não dá para desfazer.
      </ConfirmDialog>
    </main>
  );
}
