import { ArrowLeft, ChartColumn, Loader2, Plus, RotateCcw, Save } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { FiltersBar } from "@/components/dashboard/FiltersBar";
import { WidgetCard } from "@/components/dashboard/WidgetCard";
import { SmartLink } from "@/components/SmartLink";
import { buttonStyles } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import {
  configFromSpec,
  filterToSpec,
  MAX_WIDGETS,
  newWidgetConfig,
  rawFromValue,
  specFromConfig,
  type Columns,
  type FilterDraft,
  type WidgetConfig,
} from "@/lib/dashboard";
import { cn, fullDate } from "@/lib/utils";
import type { Dataset, DatasetProfile, FilterSpec, QuerySpec, SavedDashboard, WidgetSuggestion } from "@/types";

type Phase = "loading" | "ready" | "unprofiled" | "missing" | "error";
interface WidgetState {
  id: number;
  config: WidgetConfig;
}

export default function DatasetDashboard() {
  const datasetId = Number(useParams().id);
  const toast = useToast();
  const nextId = useRef(1);

  const [phase, setPhase] = useState<Phase>("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [columns, setColumns] = useState<Columns>([]);
  const [widgets, setWidgets] = useState<WidgetState[]>([]);
  const [filters, setFilters] = useState<FilterDraft[]>([]);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [computing, setComputing] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);

  const toWidgets = useCallback(
    (specs: QuerySpec[], cols: Columns): WidgetState[] =>
      specs.map((spec) => ({ id: nextId.current++, config: configFromSpec(spec, cols) })),
    [],
  );

  const loadSuggestions = useCallback(
    async (cols: Columns) => {
      const suggestions = await api<WidgetSuggestion[]>(`/datasets/${datasetId}/suggested-dashboard`);
      setWidgets(toWidgets(suggestions.map((s) => s.spec), cols));
      setSavedAt(null);
      setDirty(false);
    },
    [datasetId, toWidgets],
  );

  const init = useCallback(async () => {
    setPhase("loading");
    try {
      const list = await api<Dataset[]>("/datasets");
      const current = list.find((d) => d.id === datasetId) ?? null;
      setDataset(current);
      if (!current) return setPhase("missing");

      let profile: DatasetProfile;
      try {
        profile = await api<DatasetProfile>(`/datasets/${datasetId}/profile`);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return setPhase("unprofiled");
        throw e;
      }
      const cols = profile.columns;
      setColumns(cols);

      const saved = await api<SavedDashboard | null>(`/datasets/${datasetId}/dashboard`);
      if (saved) {
        // Filtros primeiro: cada gráfico já nasce consultando com eles aplicados.
        setFilters(
          saved.filters
            .filter((f) => cols.some((c) => c.column_name === f.column))
            .map((f) => ({ id: nextId.current++, column: f.column, op: f.op, raw: rawFromValue(f.value) })),
        );
        setWidgets(toWidgets(saved.widgets, cols));
        setSavedAt(saved.updated_at);
        setDirty(false);
      } else {
        setFilters([]);
        await loadSuggestions(cols);
      }
      setPhase("ready");
    } catch (e) {
      setErrorMessage(e instanceof Error ? e.message : "Erro inesperado.");
      setPhase("error");
    }
  }, [datasetId, loadSuggestions, toWidgets]);

  useEffect(() => {
    void init();
  }, [init]);

  const activeFilters = filters.map((f) => filterToSpec(f, columns)).filter((f): f is FilterSpec => f !== null);

  function updateWidget(id: number, config: WidgetConfig) {
    setWidgets((prev) => prev.map((w) => (w.id === id ? { ...w, config } : w)));
    setDirty(true);
  }
  function removeWidget(id: number) {
    setWidgets((prev) => prev.filter((w) => w.id !== id));
    setDirty(true);
  }
  function addWidget() {
    if (widgets.length >= MAX_WIDGETS) return toast(`Limite de ${MAX_WIDGETS} gráficos por dashboard.`, "error");
    setWidgets((prev) => [...prev, { id: nextId.current++, config: newWidgetConfig(columns) }]);
    setDirty(true);
  }
  function addFilter() {
    if (columns.length === 0) return;
    setFilters((prev) => [...prev, { id: nextId.current++, column: columns[0].column_name, op: "eq", raw: "" }]);
  }
  function changeFilter(id: number, patch: Partial<FilterDraft>) {
    setFilters((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)));
    setDirty(true);
  }
  function removeFilter(id: number) {
    setFilters((prev) => prev.filter((f) => f.id !== id));
    setDirty(true);
  }

  async function save() {
    setSaving(true);
    try {
      const saved = await api<SavedDashboard>(`/datasets/${datasetId}/dashboard`, {
        method: "PUT",
        body: JSON.stringify({ widgets: widgets.map((w) => specFromConfig(w.config, columns, [])), filters: activeFilters }),
      });
      setSavedAt(saved.updated_at);
      setDirty(false);
      toast("Dashboard salvo.");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Não foi possível salvar.", "error");
    } finally {
      setSaving(false);
    }
  }

  async function reset() {
    setConfirmReset(false);
    try {
      await api(`/datasets/${datasetId}/dashboard`, { method: "DELETE" });
      setFilters([]);
      await loadSuggestions(columns);
      toast("Painel padrão restaurado.");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Não foi possível restaurar.", "error");
    }
  }

  async function computeProfile() {
    setComputing(true);
    try {
      await api(`/datasets/${datasetId}/profile`, { method: "POST" });
      await init();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Não foi possível calcular o perfil.", "error");
    } finally {
      setComputing(false);
    }
  }

  const status = dirty ? "Alterações não salvas" : savedAt ? `Salvo em ${fullDate(savedAt)}` : "Painel padrão — ainda não salvo";

  return (
    <main className="flex flex-col gap-4 p-4 md:p-6 lg:px-7">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <SmartLink href="/app/datasets" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-accent">
            <ArrowLeft className="size-3.5" /> Datasets
          </SmartLink>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p id="dataset-name" className="truncate text-sm text-muted">
            {dataset?.original_name ?? " "}
          </p>
        </div>

        {phase === "ready" && (
          <div className="flex flex-wrap items-center gap-2">
            <span id="save-status" role="status" className={cn("text-xs", dirty ? "font-medium text-warning" : "text-muted")}>
              {status}
            </span>
            <button type="button" id="reset-dashboard" onClick={() => setConfirmReset(true)} className={buttonStyles({ variant: "secondary" })}>
              <RotateCcw className="size-4" /> Restaurar padrão
            </button>
            <button type="button" id="add-widget" onClick={addWidget} className={buttonStyles({ variant: "secondary" })}>
              <Plus className="size-4" /> Adicionar gráfico
            </button>
            <button type="button" id="save-dashboard" onClick={save} disabled={saving} className={buttonStyles({ variant: "primary" })}>
              {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />} Salvar dashboard
            </button>
          </div>
        )}
      </header>

      {phase === "loading" && (
        <div className="space-y-4" aria-busy="true">
          <Skeleton className="h-20 w-full" />
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-72 w-full" />
            ))}
          </div>
        </div>
      )}

      {phase === "unprofiled" && (
        <Card className="mx-auto mt-10 max-w-md p-8 text-center" role="status">
          <span className="mx-auto grid size-12 place-items-center rounded-xl bg-accent-soft text-accent">
            <ChartColumn className="size-6" />
          </span>
          <p className="mt-4 font-semibold">Este dataset ainda não foi perfilado</p>
          <p className="mt-1 text-sm text-muted">O perfil descobre as colunas e os tipos, e é com ele que o painel é montado.</p>
          <button type="button" onClick={computeProfile} disabled={computing} className={cn(buttonStyles({ variant: "primary" }), "mt-5")}>
            {computing && <Loader2 className="size-4 animate-spin" />} Calcular perfil e continuar
          </button>
        </Card>
      )}

      {phase === "missing" && (
        <Card className="mx-auto mt-10 max-w-md p-8 text-center" role="alert">
          <p className="font-semibold">Dataset não encontrado</p>
          <p className="mt-1 text-sm text-muted">Ele pode ter sido excluído, ou pertencer a outro usuário.</p>
          <SmartLink href="/app/datasets" className={cn(buttonStyles({ variant: "primary" }), "mt-5")}>
            Voltar aos datasets
          </SmartLink>
        </Card>
      )}

      {phase === "error" && (
        <Card className="mx-auto mt-10 max-w-md p-8 text-center" role="alert">
          <p className="font-semibold">Não foi possível montar o dashboard</p>
          <p className="mt-1 text-sm text-muted">{errorMessage}</p>
          <button type="button" onClick={() => void init()} className={cn(buttonStyles({ variant: "primary" }), "mt-5")}>
            Tentar de novo
          </button>
        </Card>
      )}

      {phase === "ready" && (
        <>
          <FiltersBar columns={columns} filters={filters} onAdd={addFilter} onChange={changeFilter} onRemove={removeFilter} />

          {widgets.length === 0 ? (
            <Card className="p-10 text-center" role="status">
              <p className="font-semibold">Nenhum gráfico</p>
              <p className="mt-1 text-sm text-muted">As regras automáticas não acharam colunas adequadas, ou você removeu todos. Use “Adicionar gráfico”.</p>
            </Card>
          ) : (
            <div id="widgets" className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,380px),1fr))] items-start gap-4">
              {widgets.map((w, index) => (
                <WidgetCard
                  key={w.id}
                  datasetId={datasetId}
                  index={index}
                  config={w.config}
                  columns={columns}
                  filters={activeFilters}
                  onChange={(config) => updateWidget(w.id, config)}
                  onRemove={() => removeWidget(w.id)}
                />
              ))}
            </div>
          )}
        </>
      )}

      <ConfirmDialog
        open={confirmReset}
        title="Restaurar painel padrão?"
        confirmLabel="Restaurar"
        onConfirm={reset}
        onCancel={() => setConfirmReset(false)}
      >
        Seus gráficos e filtros atuais, e a versão salva (se houver), serão descartados e o painel volta ao que foi gerado automaticamente.
      </ConfirmDialog>
    </main>
  );
}
