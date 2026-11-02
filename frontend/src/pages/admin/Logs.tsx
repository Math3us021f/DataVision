import { CircleAlert, Info, ListTree, RefreshCw, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { AdminPage, EmptyState, ErrorPanel } from "@/components/admin/AdminPage";
import { SearchBox } from "@/components/admin/SearchBox";
import { Stat } from "@/components/Stat";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Select } from "@/components/ui/select";
import { useApi } from "@/hooks/useApi";
import { formatNumber } from "@/lib/utils";

interface Entry {
  timestamp: string;
  level: string;
  message: string;
}

// Formato gravado pelo logging_config.py: "2026-10-24 12:34:04,608 INFO mensagem..."
const LINE_PATTERN = /^(\S+ \S+) (\w+) (.*)$/;

function parseLine(line: string): Entry {
  const match = LINE_PATTERN.exec(line);
  return match ? { timestamp: match[1], level: match[2], message: match[3] } : { timestamp: "", level: "", message: line };
}

const LEVEL_TONE = { INFO: "neutral", WARNING: "warning", ERROR: "danger" } as const;

export default function Logs() {
  const [limit, setLimit] = useState("100");
  const [level, setLevel] = useState("");
  const [search, setSearch] = useState("");
  const logs = useApi<{ lines: string[] }>(`/logs/app?limit=${limit}`);

  // O log contém texto controlado por qualquer pessoa, inclusive anônimos (ex.: o usuário digitado
  // num login falho). Por isso tudo é exibido como texto do React, nunca como HTML.
  const entries = useMemo(() => (logs.data?.lines ?? []).map(parseLine), [logs.data]);
  const counts = useMemo(() => {
    const c = { INFO: 0, WARNING: 0, ERROR: 0 };
    for (const e of entries) if (e.level in c) c[e.level as keyof typeof c] += 1;
    return c;
  }, [entries]);

  const term = search.toLowerCase();
  // Mais recentes primeiro: é o que o admin quer ver ao abrir a página.
  const visible = useMemo(
    () => entries.filter((e) => (!level || e.level === level) && (!term || e.message.toLowerCase().includes(term))).reverse(),
    [entries, level, term],
  );

  const loaded = logs.data !== null;
  const count = (n: number) => formatNumber(Math.round(n));

  return (
    <AdminPage title="Logs da aplicação" subtitle="Logins, falhas de acesso e ações administrativas. Mais recentes primeiro.">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat id="level-total" label="Linhas carregadas" icon={ListTree} loading={!loaded} value={entries.length} format={count} />
        <Stat id="level-info" label="INFO" icon={Info} loading={!loaded} value={counts.INFO} format={count} />
        <Stat id="level-warning" label="WARNING" icon={TriangleAlert} loading={!loaded} value={counts.WARNING} format={count} />
        <Stat id="level-error" label="ERROR" icon={CircleAlert} loading={!loaded} value={counts.ERROR} format={count} />
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Últimas linhas" htmlFor="logs-limit" className="w-32">
            <Select id="logs-limit" value={limit} onChange={(e) => setLimit(e.target.value)}>
              {["50", "100", "250", "500", "1000"].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Nível" htmlFor="logs-level" className="w-36">
            <Select id="logs-level" value={level} onChange={(e) => setLevel(e.target.value)}>
              <option value="">Todos</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
            </Select>
          </Field>
          <SearchBox id="logs-search" label="Buscar" placeholder="ex: Login falhou, username=..." onSearch={setSearch} />
          <button type="button" id="logs-refresh" onClick={logs.reload} className={buttonStyles({ variant: "secondary" })}>
            <RefreshCw className="size-4" /> Atualizar
          </button>
        </div>

        {logs.error && !logs.data ? (
          <div className="mt-4">
            <ErrorPanel title="Não foi possível carregar os logs" message={logs.error} />
          </div>
        ) : (
          <>
            <p id="logs-summary" className="mt-3 text-xs text-muted">
              {loaded ? `Mostrando ${visible.length} de ${entries.length} linhas carregadas.` : "Carregando..."}
            </p>
            {loaded && visible.length === 0 ? (
              <EmptyState title="Nenhuma linha encontrada" message="Tente outro termo de busca ou mude o filtro de nível." />
            ) : (
              <ol id="logs-list" className="scroll-thin mt-2 max-h-[60vh] overflow-auto rounded-lg border border-border bg-background font-mono text-xs">
                {visible.map((e, i) => (
                  <li key={i} data-level={e.level || "OTHER"} className="flex gap-3 border-b border-border px-3 py-1.5 last:border-0">
                    <span className="shrink-0 text-subtle tabular-nums">{e.timestamp}</span>
                    <span className="w-[72px] shrink-0">{e.level && <Badge tone={LEVEL_TONE[e.level as keyof typeof LEVEL_TONE] ?? "neutral"}>{e.level}</Badge>}</span>
                    <span className="min-w-0 break-words whitespace-pre-wrap">{e.message}</span>
                  </li>
                ))}
              </ol>
            )}
          </>
        )}
      </Card>
    </AdminPage>
  );
}
