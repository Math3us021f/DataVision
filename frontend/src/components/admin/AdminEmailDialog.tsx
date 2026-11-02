import { useEffect, useState, type FormEvent } from "react";

import { buttonStyles } from "@/components/ui/button";
import { Modal } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { UserRow } from "@/types";

/** O administrador define ou remove o e-mail de outra conta. Sem confirmação por e-mail: a pessoa é avisada no sistema. */
export function AdminEmailDialog({
  user,
  onClose,
  onDone,
}: {
  user: UserRow | null;
  onClose: () => void;
  onDone: (user: UserRow, updated: UserRow) => void;
}) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setEmail("");
    setError(null);
  }, [user]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!user) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api<UserRow>(`/users/${user.id}/email`, {
        method: "PATCH",
        body: JSON.stringify({ email: email.trim() || null }),
      });
      onDone(user, updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível alterar o e-mail.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={user !== null} onClose={onClose} title="E-mail de verificação">
      <form id="admin-email-form" onSubmit={submit} className="flex flex-col gap-4">
        <p>
          Conta <strong className="text-foreground">{user?.username}</strong> · atual:{" "}
          <span id="admin-email-current" className="text-foreground">{user?.email_masked ?? "nenhum"}</span>
        </p>
        <Field label="Novo e-mail (em branco remove)" htmlFor="admin-email-input">
          <Input id="admin-email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" maxLength={254} autoFocus />
        </Field>
        <p className="text-xs text-subtle">
          Não há confirmação por e-mail quando é você quem altera: a pessoa será avisada na aba de notificações do sistema e a troca fica na
          auditoria. Remover o e-mail desliga o segundo passo dessa conta.
        </p>
        {error && (
          <div id="admin-email-error" role="alert" className="rounded-lg border border-danger/40 bg-danger/10 p-3 text-foreground">
            {error}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className={buttonStyles({ variant: "secondary" })}>
            Cancelar
          </button>
          <button type="submit" id="admin-email-submit" disabled={busy} className={buttonStyles({ variant: "primary" })}>
            Salvar
          </button>
        </div>
      </form>
    </Modal>
  );
}
