import { Menu } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Sidebar } from "@/components/layout/Sidebar";
import { useSidebar } from "@/hooks/useSidebar";
import type { Me } from "@/types";

export function AppShell({ me, children }: { me: Me | null; children: ReactNode }) {
  const { collapsed, toggle } = useSidebar();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-full">
      <Sidebar me={me} collapsed={collapsed} onToggle={toggle} mobileOpen={mobileOpen} onCloseMobile={() => setMobileOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-border bg-surface px-4 py-2.5 lg:hidden">
          <button
            type="button"
            id="menu-toggle"
            onClick={() => setMobileOpen(true)}
            aria-label="Abrir menu"
            className="grid size-9 place-items-center rounded-lg text-muted hover:bg-surface-2"
          >
            <Menu className="size-5" />
          </button>
          <span className="text-[15px] font-semibold tracking-tight">DataVision</span>
        </header>
        {children}
      </div>
    </div>
  );
}
