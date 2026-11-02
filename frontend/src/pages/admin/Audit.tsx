import { useEffect, useState } from "react";

import { AdminPage, EmptyState, ErrorPanel } from "@/components/admin/AdminPage";
import { Pagination } from "@/components/admin/Pagination";
import { SearchBox } from "@/components/admin/SearchBox";
import { Card } from "@/components/ui/card";
import { Field, Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { fullDate } from "@/lib/utils";
import type { AuditLogRow, Page } from "@/types";

const PAGE_SIZE = 20;

const ACTION_LABELS: Record<string, string> = {
  create_user: "Criação de usuário",
  activate_user: "Ativação de usuário",
  deactivate_user: "Desativação de usuário",
  delete_user: "Exclusão de usuário",
  force_delete_user_datasets: "Exclusão forçada de datasets",
  reset_password: "Redefinição de senha (admin)",
  change_own_password: "Troca da própria senha",
  revoke_other_sessions: "Encerramento de outras sessões",
};

export default function Audit() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [action, setAction] = useState("");

  const actions = useApi<string[]>("/audit-logs/actions");
  const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE), search, action });
  const list = useApi<Page<AuditLogRow>>(`/audit-logs?${params}`);

  // Se a página atual deixou de existir (ex.: o filtro mudou), volta para a última.
  const total = list.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  useEffect(() => {
    if (list.data && page > pages) setPage(pages);
  }, [list.data, page, pages]);

  const filtering = search !== "" || action !== "";

  return (
    <AdminPage
      title="Auditoria"
      subtitle="Histórico de ações administrativas: criação, ativação/desativação, exclusão e redefinição de senha de usuários. Mais recentes primeiro."
    >
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <SearchBox
            id="audit-search"
            label="Buscar"
            placeholder="Nome de usuário (quem fez ou quem sofreu a ação)"
            onSearch={(term) => {
              setSearch(term);
              setPage(1);
            }}
          />
          <Field label="Ação" htmlFor="audit-action" className="w-56">
            <Select
              id="audit-action"
              value={action}
              onChange={(e) => {
                setAction(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Todas</option>
              {(actions.data ?? []).map((a) => (
                <option key={a} value={a}>
                  {ACTION_LABELS[a] ?? a}
                </option>
              ))}
            </Select>
          </Field>
          <span className="pb-2 text-xs text-muted" id="audit-count">
            {list.data ? `${total} ${total === 1 ? "registro" : "registros"}` : ""}
          </span>
        </div>

        {list.error && !list.data ? (
          <div className="mt-4">
            <ErrorPanel title="Não foi possível carregar a auditoria" message={list.error} />
          </div>
        ) : (
          <div className="scroll-thin -mx-1 mt-3 overflow-x-auto px-1">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="text-left text-[11px] font-semibold tracking-[0.08em] text-subtle uppercase">
                  <th className="py-2 pr-3 font-semibold">Quando</th>
                  <th className="px-3 py-2 font-semibold">Ação</th>
                  <th className="px-3 py-2 font-semibold">Quem fez</th>
                  <th className="px-3 py-2 font-semibold">Alvo</th>
                  <th className="py-2 pl-3 font-semibold">Detalhes</th>
                </tr>
              </thead>
              <tbody id="audit-table-body">
                {!list.data &&
                  Array.from({ length: 5 }, (_, i) => (
                    <tr key={i} className="border-t border-border">
                      <td colSpan={5} className="py-3">
                        <Skeleton className="h-6 w-full" />
                      </td>
                    </tr>
                  ))}
                {list.data?.items.map((entry) => (
                  <tr key={entry.id} className="border-t border-border transition-colors hover:bg-surface-2/60">
                    <td className="py-2.5 pr-3 whitespace-nowrap text-muted">
                      <time dateTime={entry.created_at}>{fullDate(entry.created_at)}</time>
                    </td>
                    <td className="px-3 py-2.5 font-medium">{ACTION_LABELS[entry.action] ?? entry.action}</td>
                    <td className="px-3 py-2.5">{entry.actor_username ?? "—"}</td>
                    <td className="px-3 py-2.5">{entry.target_username ?? "—"}</td>
                    <td className="py-2.5 pl-3 text-muted">{entry.details ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {list.data && list.data.items.length === 0 && (
              <EmptyState
                title="Nenhum registro encontrado"
                message={filtering ? "Tente outro termo de busca ou mude o filtro de ação." : "Nenhuma ação administrativa foi registrada ainda."}
              />
            )}
          </div>
        )}

        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
      </Card>
    </AdminPage>
  );
}
