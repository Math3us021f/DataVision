import { Check } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { AVATAR_LABELS, AVATAR_STYLES, UserAvatar } from "@/components/UserAvatar";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { Card, CardHeader, CardSubtitle, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { cn, formatBytes, formatNumber } from "@/lib/utils";
import { AVATAR_COLORS, type AvatarColor, type Profile } from "@/types";

const MAX_NAME = 60;

export function ProfileTab({ onSaved }: { onSaved: () => void }) {
  const toast = useToast();
  const profile = useApi<Profile>("/me/profile");
  const data = profile.data;

  const [name, setName] = useState("");
  const [color, setColor] = useState<AvatarColor | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setName(data.display_name ?? "");
      setColor(data.avatar_color);
    }
  }, [data]);

  const dirty = data !== null && (name.trim() !== (data.display_name ?? "") || color !== data.avatar_color);

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api<Profile>("/me/profile", { method: "PUT", body: JSON.stringify({ display_name: name.trim() || null, avatar_color: color }) });
      toast("Perfil atualizado.");
      profile.reload();
      onSaved(); // atualiza o nome/avatar no menu e na Home
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível salvar.");
    } finally {
      setSaving(false);
    }
  }

  const shownName = name.trim() || data?.username || "";

  return (
    <div className="grid gap-4 lg:grid-cols-12">
      <Card className="p-5 lg:col-span-7">
        <CardHeader>
          <div>
            <CardTitle>Seu perfil</CardTitle>
            <CardSubtitle>O nome de exibição aparece no menu e na saudação. O usuário de login não muda.</CardSubtitle>
          </div>
        </CardHeader>

        {!data ? (
          <Skeleton className="mt-5 h-56 w-full" />
        ) : (
          <form onSubmit={save} className="mt-5 space-y-5">
            <div className="flex items-center gap-4">
              <UserAvatar name={shownName} color={color} size="lg" />
              <div className="min-w-0">
                <p className="truncate text-lg font-semibold" id="profile-preview-name">
                  {shownName}
                </p>
                <p className="text-sm text-muted">@{data.username}</p>
              </div>
            </div>

            <div>
              <label htmlFor="display-name" className="text-sm font-medium">
                Nome de exibição
              </label>
              <input
                id="display-name"
                value={name}
                maxLength={MAX_NAME}
                onChange={(e) => setName(e.target.value)}
                placeholder={data.username}
                className="mt-1.5 h-10 w-full rounded-lg border border-border bg-background px-3 text-sm placeholder:text-subtle focus-visible:outline-2 focus-visible:outline-accent"
              />
              <p className="mt-1 text-right text-xs text-subtle tabular-nums">
                {name.length}/{MAX_NAME}
              </p>
            </div>

            <fieldset>
              <legend className="text-sm font-medium">Cor do avatar</legend>
              <div role="radiogroup" aria-label="Cor do avatar" className="mt-2 flex flex-wrap gap-2.5">
                {AVATAR_COLORS.map((c) => {
                  const selected = (color ?? "orange") === c;
                  return (
                    <button
                      key={c}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      aria-label={AVATAR_LABELS[c]}
                      title={AVATAR_LABELS[c]}
                      onClick={() => setColor(c === "orange" ? null : c)}
                      className={cn(
                        "grid size-10 place-items-center rounded-full ring-offset-2 ring-offset-surface transition-shadow focus-visible:outline-2 focus-visible:outline-accent",
                        AVATAR_STYLES[c],
                        selected ? "ring-2 ring-accent" : "hover:ring-2 hover:ring-border",
                      )}
                    >
                      {selected ? <Check className="size-4" /> : <span className="size-3.5 rounded-full bg-current" />}
                    </button>
                  );
                })}
              </div>
            </fieldset>

            {error && (
              <p role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}

            <button type="submit" disabled={!dirty || saving} className={buttonStyles({ variant: "primary" })}>
              {saving ? "Salvando…" : "Salvar alterações"}
            </button>
          </form>
        )}
      </Card>

      <div className="flex flex-col gap-4 lg:col-span-5">
        <Card className="p-5">
          <CardTitle>Conta</CardTitle>
          {!data ? (
            <Skeleton className="mt-4 h-24 w-full" />
          ) : (
            <dl className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-muted">Usuário</dt>
                <dd className="font-medium">{data.username}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-muted">Perfil de acesso</dt>
                <dd>{data.is_admin ? <Badge tone="accent">Administrador</Badge> : <Badge>Usuário</Badge>}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-muted">Membro desde</dt>
                <dd className="font-medium">{new Date(data.member_since).toLocaleDateString("pt-BR", { dateStyle: "long" })}</dd>
              </div>
            </dl>
          )}
        </Card>

        <Card className="p-5">
          <CardHeader className="items-center">
            <CardTitle>Seu uso</CardTitle>
            <Link to="/datasets" className="text-xs font-medium text-muted underline-offset-4 hover:text-accent hover:underline">
              Ver datasets
            </Link>
          </CardHeader>
          {!data ? (
            <Skeleton className="mt-4 h-24 w-full" />
          ) : (
            <dl id="usage" className="mt-4 grid grid-cols-2 gap-3">
              {(
                [
                  ["Datasets", formatNumber(data.usage.datasets)],
                  ["Espaço usado", formatBytes(data.usage.storage_bytes)],
                  ["Perfilados", formatNumber(data.usage.profiled)],
                  ["Dashboards salvos", formatNumber(data.usage.dashboards)],
                ] as const
              ).map(([label, value]) => (
                <div key={label} className="rounded-xl bg-surface-2 px-3 py-2.5">
                  <dt className="text-xs text-muted">{label}</dt>
                  <dd className="text-lg font-semibold tabular-nums">{value}</dd>
                </div>
              ))}
            </dl>
          )}
        </Card>
      </div>
    </div>
  );
}
