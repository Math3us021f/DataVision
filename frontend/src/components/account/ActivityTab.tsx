import { CircleAlert, CircleCheck, RefreshCw, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { Card, CardHeader, CardSubtitle, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { cn, fullDate, relativeTime } from "@/lib/utils";
import type { LoginEvent } from "@/types";

export function ActivityTab() {
  const logins = useApi<LoginEvent[]>("/me/logins");
  const events = logins.data;
  const failures = events?.filter((e) => !e.success).length ?? 0;

  return (
    <Card className="p-5">
      <CardHeader className="items-center">
        <div>
          <CardTitle>Acessos recentes</CardTitle>
          <CardSubtitle>Os últimos acessos à sua conta. Se algum não foi você, troque a senha e encerre as outras sessões.</CardSubtitle>
        </div>
        <button type="button" onClick={logins.reload} aria-label="Atualizar" title="Atualizar" className={buttonStyles({ variant: "secondary", size: "icon" })}>
          <RefreshCw className={cn("size-4", logins.loading && "animate-spin")} />
        </button>
      </CardHeader>

      {failures > 0 && (
        <p role="status" className="mt-4 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm">
          {failures === 1 ? "Houve 1 tentativa de acesso que falhou" : `Houve ${failures} tentativas de acesso que falharam`} entre os registros abaixo.
        </p>
      )}

      <ul id="login-events" className="mt-4 divide-y divide-border">
        {!events && Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="my-2 h-10 w-full" />)}
        {events?.map((event, i) => (
          <li key={`${event.created_at}-${i}`} className="flex items-center gap-3 py-3">
            <span className={cn("grid size-9 shrink-0 place-items-center rounded-lg", event.success ? "bg-success/15 text-success" : "bg-danger/15 text-danger")}>
              {event.success ? <CircleCheck className="size-4" /> : <CircleAlert className="size-4" />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{event.browser}</p>
              <p className="text-xs text-muted">{event.success ? "Acesso realizado" : "Tentativa recusada (senha incorreta ou conta inativa)"}</p>
            </div>
            {!event.success && <Badge tone="danger">Falha</Badge>}
            <time dateTime={event.created_at} title={fullDate(event.created_at)} className="shrink-0 text-xs text-muted">
              {relativeTime(event.created_at)}
            </time>
          </li>
        ))}
        {events && events.length === 0 && <li className="py-8 text-center text-sm text-muted">Nenhum acesso registrado ainda.</li>}
      </ul>

      <p className="mt-4 flex items-start gap-2 border-t border-border pt-4 text-xs text-subtle">
        <ShieldCheck className="mt-0.5 size-3.5 shrink-0" />
        Guardamos só a data, o resultado e um resumo do navegador — nunca o endereço IP — e apenas os últimos 50 acessos.
      </p>
    </Card>
  );
}
