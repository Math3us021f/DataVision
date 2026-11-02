import { Plus, X } from "lucide-react";

import { buttonStyles } from "@/components/ui/button";
import { Card, CardHeader, CardSubtitle, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { filterKindOf, OP_LABELS, opsFor, type Columns, type FilterDraft } from "@/lib/dashboard";
import type { FilterOp } from "@/types";

function ValueInput({ draft, columns, onChange }: { draft: FilterDraft; columns: Columns; onChange: (raw: string) => void }) {
  const kind = filterKindOf(columns, draft.column);
  const base =
    "h-9 w-full rounded-lg border border-border bg-background px-3 text-sm placeholder:text-subtle focus-visible:outline-2 focus-visible:outline-accent";

  if (kind === "boolean") {
    return (
      <Select aria-label="Valor do filtro" value={draft.raw === "false" ? "false" : "true"} onChange={(e) => onChange(e.target.value)}>
        <option value="true">verdadeiro</option>
        <option value="false">falso</option>
      </Select>
    );
  }
  const type = kind === "number" && draft.op !== "in" ? "number" : kind === "datetime" ? "date" : "text";
  return (
    <input
      aria-label="Valor do filtro"
      type={type}
      step={kind === "number" ? "any" : undefined}
      value={draft.raw}
      placeholder={draft.op === "in" ? "a, b, c" : "valor"}
      onChange={(e) => onChange(e.target.value)}
      className={base}
    />
  );
}

/** Filtros globais: valem para todos os gráficos. Filtro sem valor é ignorado (ainda incompleto). */
export function FiltersBar({
  columns,
  filters,
  onAdd,
  onChange,
  onRemove,
}: {
  columns: Columns;
  filters: FilterDraft[];
  onAdd: () => void;
  onChange: (id: number, patch: Partial<FilterDraft>) => void;
  onRemove: (id: number) => void;
}) {
  return (
    <Card className="p-4" data-testid="filters">
      <CardHeader className="items-center">
        <div>
          <CardTitle>Filtros globais</CardTitle>
          <CardSubtitle>Valem para todos os gráficos abaixo.</CardSubtitle>
        </div>
        <button type="button" id="add-filter" onClick={onAdd} className={`${buttonStyles({ variant: "secondary", size: "sm" })} shrink-0 whitespace-nowrap`}>
          <Plus className="size-4" /> Adicionar filtro
        </button>
      </CardHeader>

      {filters.length > 0 && (
        <div id="filters-list" className="mt-3 space-y-2">
          {filters.map((f) => {
            const kind = filterKindOf(columns, f.column);
            return (
              <div key={f.id} data-filter className="grid grid-cols-1 items-center gap-2 sm:grid-cols-[1fr_1fr_1.6fr_auto]">
                <Select
                  aria-label="Coluna do filtro"
                  value={f.column}
                  onChange={(e) => {
                    const ops = opsFor(filterKindOf(columns, e.target.value));
                    onChange(f.id, { column: e.target.value, op: ops.includes(f.op) ? f.op : ops[0], raw: "" });
                  }}
                >
                  {columns.map((c) => (
                    <option key={c.column_name} value={c.column_name}>
                      {c.column_name}
                    </option>
                  ))}
                </Select>
                <Select aria-label="Operador do filtro" value={f.op} onChange={(e) => onChange(f.id, { op: e.target.value as FilterOp })}>
                  {opsFor(kind).map((op) => (
                    <option key={op} value={op}>
                      {OP_LABELS[op]}
                    </option>
                  ))}
                </Select>
                <ValueInput draft={f} columns={columns} onChange={(raw) => onChange(f.id, { raw })} />
                <button
                  type="button"
                  onClick={() => onRemove(f.id)}
                  aria-label="Remover filtro"
                  title="Remover filtro"
                  className="grid size-9 place-items-center rounded-lg text-muted transition-colors hover:bg-danger/10 hover:text-danger"
                >
                  <X className="size-4" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
