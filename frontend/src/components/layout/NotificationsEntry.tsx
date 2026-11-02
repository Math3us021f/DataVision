import { Bell } from "lucide-react";
import { useState } from "react";

import { Drawer } from "@/components/ui/dialog";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { cn, fullDate, relativeTime } from "@/lib/utils";
import type { NotificationItem, NotificationsData } from "@/types";

const POLL_MS = 60_000;

/** Item do menu "Notificações": mostra quantos avisos não lidos há e abre a lista num painel lateral. */
export function NotificationsEntry({ collapsed }: { collapsed: boolean }) {
  // Atualiza sozinho de minuto em minuto, sem contar como atividade da pessoa (não renova a sessão).
  const notifications = useApi<NotificationsData>("/me/notifications", POLL_MS);
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState<NotificationItem[]>([]);
  const unread = notifications.data?.unread ?? 0;

  async function openPanel() {
    // O painel mostra os avisos como estavam (os novos destacados); o contador zera em seguida.
    setShown(notifications.data?.items ?? []);
    setOpen(true);
    if (unread > 0) {
      try {
        await api("/me/notifications/read", { method: "POST" });
      } finally {
        notifications.reload();
      }
    }
  }

  return (
    <>
      <button
        type="button"
        id="notifications-open"
        onClick={openPanel}
        title="Notificações"
        aria-label={unread > 0 ? `Notificações (${unread} não lidas)` : "Notificações"}
        className={cn(
          "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium text-muted transition-colors hover:bg-surface-2 hover:text-foreground",
          collapsed && "lg:justify-center lg:px-0",
        )}
      >
        <Bell className="size-[18px] shrink-0" />
        <span className={cn("flex-1 truncate", collapsed && "lg:hidden")}>Notificações</span>
        {unread > 0 && (
          <span
            id="notifications-badge"
            className={cn(
              "grid min-w-5 place-items-center rounded-full bg-accent px-1.5 text-[11px] leading-5 font-semibold text-white",
              collapsed && "lg:absolute lg:top-1 lg:right-2 lg:min-w-4 lg:px-1 lg:text-[10px] lg:leading-4",
            )}
          >
            {unread}
          </span>
        )}
      </button>

      <Drawer open={open} onClose={() => setOpen(false)} title="Notificações" subtitle="Avisos do sistema para a sua conta." className="w-[min(440px,100vw)]">
        {shown.length === 0 ? (
          <p id="notifications-empty" className="py-10 text-center text-sm text-muted">
            Nenhuma notificação por enquanto.
          </p>
        ) : (
          <ul id="notifications-list" className="flex flex-col gap-2">
            {shown.map((item) => (
              <li key={item.id} data-unread={!item.read} className={cn("rounded-lg border p-3 text-sm", item.read ? "border-border" : "border-accent/50 bg-accent-soft")}>
                <p>{item.message}</p>
                <time className="mt-1 block text-xs text-subtle" dateTime={item.created_at} title={fullDate(item.created_at)}>
                  {relativeTime(item.created_at)}
                </time>
              </li>
            ))}
          </ul>
        )}
      </Drawer>
    </>
  );
}
