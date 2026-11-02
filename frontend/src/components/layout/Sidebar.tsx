import {
  ChartLine,
  ChartNoAxesColumn,
  FileText,
  Folder,
  House,
  KeyRound,
  LogOut,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  ScrollText,
  ShieldCheck,
  Sun,
  Users,
  type LucideIcon,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { NotificationsEntry } from "@/components/layout/NotificationsEntry";
import { UserAvatar, displayNameOf } from "@/components/UserAvatar";
import { useTheme } from "@/hooks/useTheme";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Me } from "@/types";

interface Item {
  label: string;
  icon: LucideIcon;
  href: string;
}

const MAIN: Item[] = [
  { label: "Início", icon: House, href: "/" },
  { label: "Datasets", icon: FileText, href: "/datasets" },
  { label: "Minha conta", icon: KeyRound, href: "/account" },
];

const ADMIN: Item[] = [
  { label: "Usuários", icon: Users, href: "/admin/users" },
  { label: "Métricas", icon: ChartLine, href: "/admin/metrics" },
  { label: "Logs", icon: ScrollText, href: "/admin/logs" },
  { label: "Arquivos", icon: Folder, href: "/admin/files" },
  { label: "Auditoria", icon: ShieldCheck, href: "/admin/audit" },
];

function NavItem({ item, collapsed }: { item: Item; collapsed: boolean }) {
  const base =
    "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted transition-colors hover:bg-surface-2 hover:text-foreground";
  const Icon = item.icon;
  const content = (
    <>
      <Icon className="size-[18px] shrink-0" />
      <span className={cn("truncate", collapsed && "lg:hidden")}>{item.label}</span>
    </>
  );

  return (
    <NavLink
      to={item.href}
      end={item.href === "/"}
      title={item.label}
      className={({ isActive }) =>
        cn(base, collapsed && "lg:justify-center lg:px-0", isActive && "bg-accent-soft text-foreground [&_svg]:text-accent")
      }
    >
      {content}
    </NavLink>
  );
}

export function Sidebar({
  me,
  collapsed,
  onToggle,
  mobileOpen,
  onCloseMobile,
}: {
  me: Me | null;
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}) {
  const { theme, toggle: toggleTheme } = useTheme();

  async function logout() {
    try {
      await api("/logout", { method: "POST" });
    } finally {
      window.location.href = "/login";
    }
  }

  return (
    <>
      {mobileOpen && <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={onCloseMobile} aria-hidden="true" />}
      <aside
        id="sidebar"
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 -translate-x-full flex-col border-r border-border bg-surface px-3 py-4 transition-[transform,width] duration-200 lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:translate-x-0",
          mobileOpen && "translate-x-0",
          collapsed ? "lg:w-[76px]" : "lg:w-64",
        )}
      >
        <div className={cn("mb-5 flex items-center gap-3 px-1", collapsed && "lg:flex-col lg:gap-2")}>
          <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent text-white shadow-[0_6px_20px_rgb(255_90_31/0.35)]">
            <ChartNoAxesColumn className="size-5" />
          </span>
          <span className={cn("text-[15px] font-semibold tracking-tight", collapsed && "lg:hidden")}>DataVision</span>
          <button
            type="button"
            id="sidebar-collapse"
            onClick={onToggle}
            aria-label={collapsed ? "Expandir menu" : "Recolher menu"}
            aria-expanded={!collapsed}
            title={collapsed ? "Expandir menu" : "Recolher menu"}
            className={cn(
              "ml-auto hidden size-8 place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-foreground lg:grid",
              collapsed && "lg:ml-0",
            )}
          >
            {collapsed ? <PanelLeftOpen className="size-[18px]" /> : <PanelLeftClose className="size-[18px]" />}
          </button>
        </div>

        <nav aria-label="Principal" className="flex flex-col gap-0.5">
          {MAIN.map((item) => (
            <NavItem key={item.href} item={item} collapsed={collapsed} />
          ))}
          {me && <NotificationsEntry collapsed={collapsed} />}
        </nav>

        {me?.is_admin && (
          <>
            <div className={cn("px-3 pt-5 pb-1.5 text-[10px] font-semibold tracking-[0.12em] text-subtle uppercase", collapsed && "lg:hidden")}>
              Administração
            </div>
            {collapsed && <div className="mx-3 my-3 hidden h-px bg-border lg:block" />}
            <nav aria-label="Administração" className="flex flex-col gap-0.5">
              {ADMIN.map((item) => (
                <NavItem key={item.href} item={item} collapsed={collapsed} />
              ))}
            </nav>
          </>
        )}

        <div className={cn("mt-auto flex items-center gap-2 border-t border-border pt-3", collapsed && "lg:flex-col")}>
          {me ? (
            <span title={displayNameOf(me)} className="shrink-0">
              <UserAvatar name={displayNameOf(me)} color={me.avatar_color} />
            </span>
          ) : (
            <span className="size-9 shrink-0 rounded-full bg-surface-2" />
          )}
          <div className={cn("min-w-0 flex-1", collapsed && "lg:hidden")}>
            <p id="sidebar-user-name" className="truncate text-sm font-medium">{me ? displayNameOf(me) : "…"}</p>
            <p className="text-xs text-subtle">{me?.is_admin ? "Administrador" : "Usuário"}</p>
          </div>
          <button
            type="button"
            onClick={toggleTheme}
            aria-label="Alternar tema claro/escuro"
            title="Alternar tema claro/escuro"
            className="grid size-8 place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
          >
            {theme === "dark" ? <Sun className="size-[18px]" /> : <Moon className="size-[18px]" />}
          </button>
          <button
            type="button"
            id="logout-button"
            onClick={logout}
            aria-label="Sair"
            title="Sair"
            className="grid size-8 place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-danger"
          >
            <LogOut className="size-[18px]" />
          </button>
        </div>
      </aside>
    </>
  );
}
