import { useEffect, useState, type FormEvent } from "react";

import { buttonStyles } from "@/components/ui/button";
import { Modal } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { UserRow } from "@/types";

export function ResetPasswordDialog({
  user,
  onClose,
  onDone,
}: {
  user: UserRow | null;
  onClose: () => void;
  onDone: (user: UserRow) => void;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setPassword("");
    setError(null);
  }, [user]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!user) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/users/${user.id}/password`, { method: "PUT", body: JSON.stringify({ new_password: password }) });
      onDone(user);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível redefinir a senha.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={user !== null} onClose={onClose} title="Redefinir senha">
      <form id="reset-form" onSubmit={submit} className="flex flex-col gap-4">
        <p>
          Nova senha para <strong className="text-foreground">{user?.username}</strong>. Sessões abertas dessa pessoa serão encerradas.
        </p>
        <Field label="Nova senha (mínimo 8 caracteres)" htmlFor="reset-password">
          <Input id="reset-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" minLength={8} required autoFocus />
        </Field>
        {error && (
          <div id="reset-error" role="alert" className="rounded-lg border border-danger/40 bg-danger/10 p-3 text-foreground">
            {error}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className={buttonStyles({ variant: "secondary" })}>
            Cancelar
          </button>
          <button type="submit" id="reset-submit" disabled={busy} className={buttonStyles({ variant: "primary" })}>
            Redefinir
          </button>
        </div>
      </form>
    </Modal>
  );
}
