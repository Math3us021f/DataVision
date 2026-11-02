import { ChartColumn, LayoutDashboard, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ColumnCard } from "@/components/datasets/ColumnCard";
import { buttonStyles } from "@/components/ui/button";
import { Drawer } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { formatBytes, formatNumber } from "@/lib/utils";
import type { Dataset, DatasetProfile, DatasetSample } from "@/types";

type ProfileState =
  | { kind: "loading" }
  | { kind: "empty" } // ainda não perfilado
  | { kind: "error"; message: string }
  | { kind: "ready"; profile: DatasetProfile };

type SampleState = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; sample: DatasetSample };

function Message({ title, children }: { title: string; children?: string }) {
  return (
    <div role="status" className="rounded-xl border border-dashed border-border py-10 text-center">
      <p className="text-sm font-semibold">{title}</p>
      {children && <p className="mx-auto mt-1 max-w-sm text-sm text-muted">{children}</p>}
    </div>
  );
}

function SampleTable({ sample }: { sample: DatasetSample }) {
  return (
    <section aria-label="Amostra dos dados">
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">Amostra dos dados</h3>
        <span className="text-xs text-muted">
          {sample.sample_size} de {formatNumber(sample.total_rows)} linha(s)
        </span>
      </div>
      <div className="scroll-thin max-h-64 overflow-auto rounded-xl border border-border">
        <table className="w-full min-w-max text-xs">
          <thead className="sticky top-0 bg-surface-2">
            <tr>
              {sample.columns.map((name, i) => (
                <th key={i} className="px-3 py-2 text-left font-semibold whitespace-nowrap">
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sample.rows.map((row, r) => (
              <tr key={r} className="border-t border-border">
                {row.map((cell, c) => (
                  <td key={c} className={cell === null ? "px-3 py-1.5 text-subtle" : "px-3 py-1.5 whitespace-nowrap"}>
                    {cell === null ? "—" : cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** Perfil do dataset: números gerais, amostra e um cartão (com gráfico) por coluna. */
export function ProfileDrawer({
  dataset,
  onClose,
  onProfiled,
}: {
  dataset: Dataset | null;
  onClose: () => void;
  onProfiled: () => void;
}) {
  const toast = useToast();
  const [profile, setProfile] = useState<ProfileState>({ kind: "loading" });
  const [sample, setSample] = useState<SampleState>({ kind: "loading" });
  const [calculating, setCalculating] = useState(false);
  const id = dataset?.id;

  useEffect(() => {
    if (id === undefined) return;
    const controller = new AbortController();
    setProfile({ kind: "loading" });
    setSample({ kind: "loading" });

    api<DatasetSample>(`/datasets/${id}/sample`, {}, controller.signal)
      .then((s) => setSample({ kind: "ready", sample: s }))
      .catch((e: unknown) => !controller.signal.aborted && setSample({ kind: "error", message: e instanceof Error ? e.message : "Erro" }));

    api<DatasetProfile>(`/datasets/${id}/profile`, {}, controller.signal)
      .then((p) => setProfile({ kind: "ready", profile: p }))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 404) setProfile({ kind: "empty" });
        else setProfile({ kind: "error", message: e instanceof Error ? e.message : "Erro" });
      });

    return () => controller.abort();
  }, [id]);

  const calculate = useCallback(async () => {
    if (id === undefined) return;
    setCalculating(true);
    try {
      const p = await api<DatasetProfile>(`/datasets/${id}/profile`, { method: "POST" });
      setProfile({ kind: "ready", profile: p });
      toast("Perfil calculado.");
      onProfiled();
    } catch (e) {
      setProfile({ kind: "error", message: e instanceof Error ? e.message : "Erro" });
    } finally {
      setCalculating(false);
    }
  }, [id, onProfiled, toast]);

  const ready = profile.kind === "ready" ? profile.profile : null;

  return (
    <Drawer
      open={dataset !== null}
      onClose={onClose}
      title="Perfilamento"
      subtitle={dataset ? `${dataset.original_name} · ${formatBytes(dataset.size_bytes)}` : undefined}
      footer={
        dataset && (
          <>
            <a href={`/meus-datasets/${dataset.id}/dashboard`} className={buttonStyles({ variant: "secondary" })}>
              <LayoutDashboard className="size-4" /> Abrir dashboard
            </a>
            <button type="button" id="profile-recalculate" onClick={calculate} disabled={calculating} className={buttonStyles({ variant: "primary" })}>
              {calculating ? <Loader2 className="size-4 animate-spin" /> : profile.kind === "empty" ? <ChartColumn className="size-4" /> : <RefreshCw className="size-4" />}
              {calculating ? "Calculando…" : profile.kind === "empty" ? "Calcular perfil" : "Recalcular"}
            </button>
          </>
        )
      }
    >
      <div className="space-y-6">
        {profile.kind === "loading" && (
          <div className="space-y-3">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        )}
        {profile.kind === "empty" && (
          <Message title="Ainda não perfilado">Clique em “Calcular perfil” para analisar as colunas deste arquivo.</Message>
        )}
        {profile.kind === "error" && <Message title="Não foi possível carregar o perfil">{profile.message}</Message>}

        {ready && (
          <dl className="grid grid-cols-3 gap-3" id="profile-summary">
            {(
              [
                ["Linhas", ready.row_count],
                ["Linhas duplicadas", ready.duplicate_row_count],
                ["Colunas", ready.columns.length],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="rounded-xl border border-border bg-background/40 px-4 py-3">
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="text-xl font-semibold tabular-nums">{formatNumber(value)}</dd>
              </div>
            ))}
          </dl>
        )}

        {sample.kind === "loading" && <Skeleton className="h-32 w-full" />}
        {sample.kind === "error" && <Message title="Não foi possível carregar a amostra">{sample.message}</Message>}
        {sample.kind === "ready" && <SampleTable sample={sample.sample} />}

        {ready && (
          <section aria-label="Colunas">
            <h3 className="mb-3 text-sm font-semibold">Colunas</h3>
            <div className="grid gap-4 md:grid-cols-2">
              {ready.columns.map((column, i) => (
                <ColumnCard key={`${column.column_name}-${i}`} column={column} totalRows={ready.row_count} />
              ))}
            </div>
          </section>
        )}
      </div>
    </Drawer>
  );
}
