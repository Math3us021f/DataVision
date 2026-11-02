import { KeyRound, Plus, Power, ShieldCheck, Trash2, UserCheck, UserX, Users as UsersIcon, type LucideIcon } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { AdminPage, EmptyState, ErrorPanel } from "@/components/admin/AdminPage";
import { CreateUserDrawer } from "@/components/admin/CreateUserDrawer";
import { Pagination } from "@/components/admin/Pagination";
import { ResetPasswordDialog } from "@/components/admin/ResetPasswordDialog";
import { SearchBox } from "@/components/admin/SearchBox";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Stat } from "@/components/Stat";
import { UserAvatar } from "@/components/UserAvatar";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { cn, formatNumber } from "@/lib/utils";
import type { Me, Page, UserRow, UsersSummary } from "@/types";

const PAGE_SIZE = 20;

interface Pending {
  title: string;
  body: ReactNode;
  label: string;
  run: () => Promise<void>;
}

interface Failure {
  user: UserRow;
  err: unknown;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
const messageOf = (err: unknown) => (err instanceof Error ? err.message : "Erro inesperado");

function RowButton({ label, icon: Icon, onClick, danger }: { label: string; icon: LucideIcon; onClick: () => void; danger?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        "grid size-8 place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-foreground",
        danger && "hover:bg-danger/10 hover:text-danger",
      )}
    >
      <Icon className="size-4" />
    </button>
  );
}

export default function Users({ me }: { me: Me }) {
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  // Seleção guardada por id: sobrevive à troca de página e à busca.
  const [selected, setSelected] = useState<Map<number, UserRow>>(new Map());
  const [creating, setCreating] = useState(false);
  const [resetting, setResetting] = useState<UserRow | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);

  const summary = useApi<UsersSummary>("/users/summary");
  const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE), status, search });
  const list = useApi<Page<UserRow>>(`/users?${params}`);

  const total = list.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  useEffect(() => {
    if (list.data && page > pages) setPage(pages);
  }, [list.data, page, pages]);

  const items = list.data?.items ?? [];
  const selectable = items.filter((u) => u.username !== me.username); // a própria conta não entra em ações em lote
  const checkedOnPage = selectable.filter((u) => selected.has(u.id)).length;
  const allChecked = selectable.length > 0 && checkedOnPage === selectable.length;

  function refresh() {
    list.reload();
    summary.reload();
  }

  function toggle(user: UserRow, checked: boolean) {
    setSelected((prev) => {
      const next = new Map(prev);
      if (checked) next.set(user.id, user);
      else next.delete(user.id);
      return next;
    });
  }

  function toggleAll(checked: boolean) {
    setSelected((prev) => {
      const next = new Map(prev);
      for (const u of selectable) {
        if (checked) next.set(u.id, u);
        else next.delete(u.id);
      }
      return next;
    });
  }

  // Chama o endpoint de cada usuário, um por vez: cada um passa pelas mesmas validações e entra
  // na auditoria individualmente. Falhas não interrompem o lote.
  async function runBulk(users: UserRow[], request: (u: UserRow) => Promise<unknown>) {
    let ok = 0;
    const failures: Failure[] = [];
    for (const user of users) {
      try {
        await request(user);
        ok += 1;
        setSelected((prev) => {
          const next = new Map(prev);
          next.delete(user.id);
          return next;
        });
      } catch (err) {
        failures.push({ user, err });
      }
    }
    return { ok, failures };
  }

  function report(result: { ok: number; failures: Failure[] }, verb: string) {
    if (result.ok) toast(`${plural(result.ok, "usuário", "usuários")} ${verb}.`);
    if (result.failures.length) {
      const first = result.failures[0];
      toast(`${result.failures.length} não ${result.failures.length === 1 ? "pôde" : "puderam"} ser ${verb}. ${first.user.username}: ${messageOf(first.err)}`, "error");
    }
  }

  const setActive = (u: UserRow, is_active: boolean) => api(`/users/${u.id}`, { method: "PATCH", body: JSON.stringify({ is_active }) });

  async function activate(user: UserRow) {
    try {
      await setActive(user, true);
      toast(`Usuário "${user.username}" ativado.`);
      refresh();
    } catch (err) {
      toast(messageOf(err), "error");
    }
  }

  function askDeactivate(user: UserRow) {
    setPending({
      title: "Desativar usuário?",
      body: `"${user.username}" não conseguirá mais entrar, e sessões abertas deixam de valer imediatamente. Dá para reativar depois.`,
      label: "Desativar",
      run: async () => {
        try {
          await setActive(user, false);
          toast(`Usuário "${user.username}" desativado.`);
          refresh();
        } catch (err) {
          toast(messageOf(err), "error");
        }
      },
    });
  }

  function askDelete(user: UserRow) {
    setPending({
      title: "Excluir usuário permanentemente?",
      body: `"${user.username}" será apagado e não poderá ser recuperado. O histórico de auditoria é mantido. Se a ideia é só bloquear o acesso, prefira Desativar.`,
      label: "Excluir",
      run: async () => {
        try {
          await api(`/users/${user.id}`, { method: "DELETE" });
          toggle(user, false);
          toast(`Usuário "${user.username}" excluído.`);
          refresh();
        } catch (err) {
          // Usuário com datasets: o servidor recusou (409) e explicou o motivo. Exige uma segunda confirmação.
          if (err instanceof ApiError && err.status === 409) askForceDelete(user, err.message);
          else toast(messageOf(err), "error");
        }
      },
    });
  }

  function askForceDelete(user: UserRow, reason: string) {
    setPending({
      title: "Apagar também os datasets?",
      body: `${reason} Esta segunda confirmação apaga TUDO: usuário, datasets e arquivos no MinIO, sem volta.`,
      label: "Apagar tudo",
      run: async () => {
        try {
          await api(`/users/${user.id}?force=true`, { method: "DELETE" });
          toggle(user, false);
          toast(`Usuário "${user.username}" e seus datasets foram excluídos.`);
          refresh();
        } catch (err) {
          toast(messageOf(err), "error");
        }
      },
    });
  }

  async function bulkActivate() {
    report(await runBulk([...selected.values()], (u) => setActive(u, true)), "ativados");
    refresh();
  }

  function askBulkDeactivate() {
    const users = [...selected.values()];
    setPending({
      title: `Desativar ${plural(users.length, "usuário", "usuários")}?`,
      body: "Eles não conseguirão mais entrar, e sessões abertas deixam de valer imediatamente. Dá para reativar depois.",
      label: "Desativar",
      run: async () => {
        report(await runBulk(users, (u) => setActive(u, false)), "desativados");
        refresh();
      },
    });
  }

  function askBulkDelete() {
    const users = [...selected.values()];
    setPending({
      title: `Excluir ${plural(users.length, "usuário", "usuários")} permanentemente?`,
      body: "Não dá para desfazer. O histórico de auditoria é mantido. Quem tiver datasets será pulado nesta primeira passada — você poderá optar por apagar os dados deles também, em seguida.",
      label: `Excluir ${users.length}`,
      run: async () => {
        const first = await runBulk(users, (u) => api(`/users/${u.id}`, { method: "DELETE" }));
        if (first.ok) toast(`${plural(first.ok, "usuário excluído", "usuários excluídos")}.`);
        const withDatasets = first.failures.filter((f) => f.err instanceof ApiError && f.err.status === 409);
        const others = first.failures.filter((f) => !withDatasets.includes(f));
        if (others.length) toast(`${others.length} não ${others.length === 1 ? "pôde" : "puderam"} ser excluído(s): ${others[0].user.username}: ${messageOf(others[0].err)}`, "error");
        refresh();

        if (withDatasets.length) {
          setPending({
            title: `Apagar também os datasets de ${plural(withDatasets.length, "usuário", "usuários")}?`,
            body: "Esta segunda confirmação apaga usuário, datasets e os arquivos correspondentes no MinIO, de todos os selecionados abaixo. Sem volta.",
            label: "Apagar tudo",
            run: async () => {
              const second = await runBulk(withDatasets.map((f) => f.user), (u) => api(`/users/${u.id}?force=true`, { method: "DELETE" }));
              report(second, "excluídos (com datasets)");
              refresh();
            },
          });
        }
      },
    });
  }

  async function confirm() {
    const current = pending;
    if (!current) return;
    setPending(null);
    await current.run();
  }

  const s = summary.data;
  const filtering = search !== "" || status !== "all";

  return (
    <AdminPage
      title="Usuários"
      subtitle="Contas com acesso ao DataVision. Não existe cadastro público."
      actions={
        <button type="button" id="new-user-button" onClick={() => setCreating(true)} className={buttonStyles({ variant: "primary" })}>
          <Plus className="size-4" /> Novo usuário
        </button>
      }
    >
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat id="summary-total" label="Total de contas" icon={UsersIcon} loading={!s} value={s?.total ?? null} format={(n) => formatNumber(Math.round(n))} />
        <Stat
          id="summary-active"
          label="Ativas"
          icon={UserCheck}
          loading={!s}
          value={s?.active ?? null}
          format={(n) => formatNumber(Math.round(n))}
          detail={s && s.total > 0 ? `${Math.round((s.active / s.total) * 100)}% do total` : ""}
        />
        <Stat id="summary-inactive" label="Inativas" icon={UserX} loading={!s} value={s?.inactive ?? null} format={(n) => formatNumber(Math.round(n))} />
        <Stat id="summary-admins" label="Administradores" icon={ShieldCheck} loading={!s} value={s?.admins ?? null} format={(n) => formatNumber(Math.round(n))} />
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <SearchBox
            id="users-search"
            label="Buscar"
            placeholder="Nome de usuário"
            onSearch={(term) => {
              setSearch(term);
              setPage(1);
            }}
          />
          <Field label="Status" htmlFor="users-status" className="w-40">
            <Select
              id="users-status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="all">Todos</option>
              <option value="active">Ativos</option>
              <option value="inactive">Inativos</option>
            </Select>
          </Field>
          <span className="pb-2 text-xs text-muted" id="users-count">
            {list.data ? plural(total, "usuário", "usuários") : ""}
          </span>
        </div>

        {selected.size > 0 && (
          <div id="bulk-bar" className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-accent/40 bg-accent-soft px-3 py-2 text-sm">
            <span id="bulk-count" className="font-medium">
              {plural(selected.size, "usuário selecionado", "usuários selecionados")}
            </span>
            <div className="flex flex-wrap gap-1.5">
              <button type="button" id="bulk-activate" onClick={bulkActivate} className={buttonStyles({ size: "sm" })}>
                Ativar
              </button>
              <button type="button" id="bulk-deactivate" onClick={askBulkDeactivate} className={buttonStyles({ size: "sm" })}>
                Desativar
              </button>
              <button type="button" id="bulk-delete" onClick={askBulkDelete} className={cn(buttonStyles({ size: "sm" }), "text-danger")}>
                Excluir
              </button>
              <button type="button" id="bulk-clear" onClick={() => setSelected(new Map())} className={buttonStyles({ variant: "ghost", size: "sm" })}>
                Limpar seleção
              </button>
            </div>
          </div>
        )}

        {list.error && !list.data ? (
          <div className="mt-4">
            <ErrorPanel title="Não foi possível carregar os usuários" message={list.error} />
          </div>
        ) : (
          <div className="scroll-thin -mx-1 mt-3 overflow-x-auto px-1">
            <table id="users-table" className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="text-left text-[11px] font-semibold tracking-[0.08em] text-subtle uppercase">
                  <th className="w-8 py-2 pr-2">
                    <input
                      type="checkbox"
                      id="select-all"
                      aria-label="Selecionar todos desta página"
                      checked={allChecked}
                      ref={(el) => {
                        if (el) el.indeterminate = checkedOnPage > 0 && !allChecked;
                      }}
                      disabled={selectable.length === 0}
                      onChange={(e) => toggleAll(e.target.checked)}
                      className="size-4 accent-accent"
                    />
                  </th>
                  <th className="px-3 py-2 font-semibold">Usuário</th>
                  <th className="px-3 py-2 font-semibold">Perfil</th>
                  <th className="px-3 py-2 font-semibold">Status</th>
                  <th className="py-2 pl-3" />
                </tr>
              </thead>
              <tbody id="users-table-body">
                {!list.data &&
                  Array.from({ length: 5 }, (_, i) => (
                    <tr key={i} className="border-t border-border">
                      <td colSpan={5} className="py-3">
                        <Skeleton className="h-8 w-full" />
                      </td>
                    </tr>
                  ))}
                {items.map((user) => {
                  const isMe = user.username === me.username;
                  return (
                    <tr
                      key={user.id}
                      data-user={user.username}
                      className={cn("border-t border-border transition-colors hover:bg-surface-2/60", selected.has(user.id) && "bg-accent-soft/50")}
                    >
                      <td className="py-2.5 pr-2">
                        <input
                          type="checkbox"
                          aria-label={`Selecionar ${user.username}`}
                          checked={selected.has(user.id)}
                          disabled={isMe}
                          onChange={(e) => toggle(user, e.target.checked)}
                          className="size-4 accent-accent"
                        />
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-3">
                          <UserAvatar name={user.username} color={null} />
                          <span className="font-medium">{user.username}</span>
                          {isMe && <Badge>você</Badge>}
                        </div>
                      </td>
                      <td className="px-3 py-2.5">{user.is_admin ? <Badge tone="accent">Administrador</Badge> : <Badge>Usuário</Badge>}</td>
                      <td className="px-3 py-2.5">{user.is_active ? <Badge tone="success">Ativo</Badge> : <Badge tone="danger">Inativo</Badge>}</td>
                      <td className="py-2.5 pl-3">
                        {isMe ? (
                          // A própria conta não tem ações aqui: a senha se troca em "Minha conta".
                          <span className="block text-right text-muted">—</span>
                        ) : (
                          <div className="flex items-center justify-end gap-0.5">
                            <RowButton label={`Redefinir senha de ${user.username}`} icon={KeyRound} onClick={() => setResetting(user)} />
                            {user.is_active ? (
                              <RowButton label={`Desativar ${user.username}`} icon={Power} onClick={() => askDeactivate(user)} />
                            ) : (
                              <RowButton label={`Ativar ${user.username}`} icon={Power} onClick={() => activate(user)} />
                            )}
                            <RowButton label={`Excluir ${user.username}`} icon={Trash2} danger onClick={() => askDelete(user)} />
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {list.data && items.length === 0 && (
              <EmptyState
                title="Nenhum usuário encontrado"
                message={filtering ? "Tente outro termo de busca ou mude o filtro de status." : "Crie o primeiro usuário pelo botão “Novo usuário”."}
              />
            )}
          </div>
        )}

        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
      </Card>

      <CreateUserDrawer
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(user) => {
          setCreating(false);
          toast(`Usuário "${user.username}" criado.`);
          refresh();
        }}
      />
      <ResetPasswordDialog
        user={resetting}
        onClose={() => setResetting(null)}
        onDone={(user) => {
          setResetting(null);
          toast(`Senha de "${user.username}" redefinida.`);
        }}
      />
      <ConfirmDialog open={pending !== null} title={pending?.title ?? ""} confirmLabel={pending?.label ?? ""} danger onConfirm={confirm} onCancel={() => setPending(null)}>
        {pending?.body}
      </ConfirmDialog>
    </AdminPage>
  );
}
