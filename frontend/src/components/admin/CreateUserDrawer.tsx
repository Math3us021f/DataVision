import { useEffect, useState, type FormEvent } from "react";

import { buttonStyles } from "@/components/ui/button";
import { Drawer } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { UserRow } from "@/types";

export function CreateUserDrawer({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (user: UserRow) => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setUsername("");
      setPassword("");
      setIsAdmin(false);
      setEmail("");
      setError(null);
    }
  }, [open]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api<UserRow>("/users", {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password, is_admin: isAdmin, email: email.trim() || null }),
      });
      onCreated(created);
    } catch (e) {
      // O erro aparece dentro do painel, ao lado do formulário que o causou.
      setError(e instanceof Error ? e.message : "Não foi possível criar o usuário.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Drawer open={open} onClose={onClose} title="Novo usuário" subtitle="A conta fica ativa assim que é criada." className="w-[min(440px,100vw)]">
      <form id="create-user-form" onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Usuário" htmlFor="new-username">
          <Input id="new-username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="off" required />
        </Field>
        <Field label="Senha inicial" htmlFor="new-password">
          <Input
            id="new-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
          <p className="mt-1 text-xs text-subtle">Mínimo de 8 caracteres. A pessoa pode trocá-la depois em “Minha conta”.</p>
        </Field>
        <Field label="E-mail (opcional)" htmlFor="new-email">
          <Input id="new-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" maxLength={254} />
          <p className="mt-1 text-xs text-subtle">
            Com e-mail, a pessoa recebe um código a cada login (verificação em dois passos). Sem e-mail, entra só com a senha.
          </p>
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input id="new-is-admin" type="checkbox" checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)} className="size-4 accent-accent" />
          Administrador
        </label>
        {error && (
          <div id="create-user-error" role="alert" className="rounded-lg border border-danger/40 bg-danger/10 p-3 text-sm">
            {error}
          </div>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className={buttonStyles({ variant: "secondary" })}>
            Cancelar
          </button>
          <button type="submit" id="create-user-submit" disabled={busy} className={buttonStyles({ variant: "primary" })}>
            Criar usuário
          </button>
        </div>
      </form>
    </Drawer>
  );
}
