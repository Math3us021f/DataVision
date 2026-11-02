import { History, ShieldCheck, UserRound, type LucideIcon } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { ActivityTab } from "@/components/account/ActivityTab";
import { ProfileTab } from "@/components/account/ProfileTab";
import { SecurityTab } from "@/components/account/SecurityTab";
import { UserAvatar, displayNameOf } from "@/components/UserAvatar";
import { cn } from "@/lib/utils";
import type { Me } from "@/types";

const TABS: { key: string; label: string; icon: LucideIcon }[] = [
  { key: "perfil", label: "Perfil", icon: UserRound },
  { key: "seguranca", label: "Segurança", icon: ShieldCheck },
  { key: "atividade", label: "Atividade", icon: History },
];

export default function Account({ me, onSaved }: { me: Me; onSaved: () => void }) {
  const [params, setParams] = useSearchParams();
  const requested = params.get("aba");
  const active = TABS.some((t) => t.key === requested) ? (requested as string) : "perfil";

  return (
    <main className="flex flex-col gap-5 p-4 md:p-6 lg:px-7">
      <header className="flex items-center gap-4">
        <UserAvatar name={displayNameOf(me)} color={me.avatar_color} size="md" />
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight">Minha conta</h1>
          <p className="truncate text-sm text-muted">
            {displayNameOf(me)} · {me.is_admin ? "Administrador" : "Usuário"}
          </p>
        </div>
      </header>

      <div role="tablist" aria-label="Seções da conta" className="flex gap-1 border-b border-border">
        {TABS.map(({ key, label, icon: Icon }) => {
          const selected = key === active;
          return (
            <button
              key={key}
              type="button"
              role="tab"
              id={`tab-${key}`}
              aria-selected={selected}
              aria-controls={`panel-${key}`}
              onClick={() => setParams(key === "perfil" ? {} : { aba: key }, { replace: true })}
              className={cn(
                "-mb-px flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-accent",
                selected ? "border-accent text-foreground" : "border-transparent text-muted hover:text-foreground",
              )}
            >
              <Icon className="size-4" />
              {label}
            </button>
          );
        })}
      </div>

      <div role="tabpanel" id={`panel-${active}`} aria-labelledby={`tab-${active}`}>
        {active === "perfil" && <ProfileTab onSaved={onSaved} />}
        {active === "seguranca" && <SecurityTab />}
        {active === "atividade" && <ActivityTab />}
      </div>
    </main>
  );
}
