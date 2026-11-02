import { Check, Eye, EyeOff, LogOut, X } from "lucide-react";
import { useState, type FormEvent } from "react";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { buttonStyles } from "@/components/ui/button";
import { Card, CardSubtitle, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { byteLength, MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH, passwordStrength } from "@/lib/password";
import { cn } from "@/lib/utils";

function PasswordField({
  id,
  label,
  value,
  onChange,
  autoComplete,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <div className="relative mt-1.5">
        <input
          id={id}
          type={visible ? "text" : "password"}
          value={value}
          autoComplete={autoComplete}
          onChange={(e) => onChange(e.target.value)}
          className="h-10 w-full rounded-lg border border-border bg-background pr-11 pl-3 text-sm focus-visible:outline-2 focus-visible:outline-accent"
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? `Ocultar ${label.toLowerCase()}` : `Mostrar ${label.toLowerCase()}`}
          className="absolute top-1/2 right-1.5 grid size-7 -translate-y-1/2 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-foreground"
        >
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
    </div>
  );
}

function Rule({ ok, children }: { ok: boolean; children: string }) {
  return (
    <li className={cn("flex items-center gap-2 text-xs", ok ? "text-success" : "text-muted")}>
      {ok ? <Check className="size-3.5" /> : <X className="size-3.5 opacity-60" />}
      <span>{children}</span>
    </li>
  );
}

const STRENGTH_COLORS = ["bg-danger", "bg-danger", "bg-warning", "bg-success", "bg-success"];

export function SecurityTab() {
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const [revoking, setRevoking] = useState(false);

  const strength = passwordStrength(next);
  const longEnough = next.length >= MIN_PASSWORD_LENGTH;
  const bytesOk = byteLength(next) <= MAX_PASSWORD_BYTES;
  const differs = next.length > 0 && next !== current;
  const matches = next.length > 0 && next === confirm;
  const valid = current.length > 0 && longEnough && bytesOk && differs && matches;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api("/me/password", { method: "PUT", body: JSON.stringify({ current_password: current, new_password: next }) });
      toast("Senha alterada. Suas outras sessões foram encerradas.");
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível alterar a senha.");
    } finally {
      setSaving(false);
    }
  }

  async function revokeOthers() {
    setRevoking(true);
    try {
      await api("/me/sessions/revoke-others", { method: "POST" });
      toast("Outras sessões encerradas.");
      setConfirmRevoke(false);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Não foi possível encerrar as sessões.", "error");
    } finally {
      setRevoking(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-12">
      <Card className="p-5 lg:col-span-7">
        <CardTitle>Trocar senha</CardTitle>
        <CardSubtitle>Ao trocar, suas outras sessões abertas (outros navegadores ou computadores) são encerradas.</CardSubtitle>

        <form onSubmit={submit} className="mt-5 space-y-4">
          <PasswordField id="current-password" label="Senha atual" value={current} onChange={setCurrent} autoComplete="current-password" />
          <PasswordField id="new-password" label="Nova senha" value={next} onChange={setNext} autoComplete="new-password" />

          <div aria-live="polite">
            <div className="flex gap-1.5" aria-hidden="true">
              {[1, 2, 3, 4].map((step) => (
                <span key={step} className={cn("h-1.5 flex-1 rounded-full bg-surface-2 transition-colors", next && strength.score >= step && STRENGTH_COLORS[strength.score])} />
              ))}
            </div>
            <p id="strength-label" className="mt-1.5 text-xs text-muted">
              {next ? `Força: ${strength.label}` : "Digite a nova senha para ver a força."}
            </p>
          </div>

          <ul className="space-y-1.5" aria-label="Requisitos da senha">
            <Rule ok={longEnough}>{`Pelo menos ${MIN_PASSWORD_LENGTH} caracteres`}</Rule>
            <Rule ok={next.length === 0 || bytesOk}>{`No máximo ${MAX_PASSWORD_BYTES} bytes`}</Rule>
            <Rule ok={differs}>Diferente da senha atual</Rule>
          </ul>

          <PasswordField id="confirm-password" label="Confirmar nova senha" value={confirm} onChange={setConfirm} autoComplete="new-password" />
          {confirm.length > 0 && !matches && <p className="-mt-2 text-xs text-danger">As senhas não conferem.</p>}

          {error && (
            <p role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}

          <button type="submit" id="password-submit" disabled={!valid || saving} className={buttonStyles({ variant: "primary" })}>
            {saving ? "Salvando…" : "Salvar nova senha"}
          </button>
        </form>
      </Card>

      <Card className="h-fit p-5 lg:col-span-5">
        <CardTitle>Sessões</CardTitle>
        <CardSubtitle>
          Se você entrou em um computador que não é seu, ou suspeita de algo estranho, encerre todas as outras sessões. Esta continua aberta.
        </CardSubtitle>
        <button type="button" id="revoke-others" onClick={() => setConfirmRevoke(true)} className={cn(buttonStyles({ variant: "secondary" }), "mt-4")}>
          <LogOut className="size-4" /> Encerrar outras sessões
        </button>
      </Card>

      <ConfirmDialog
        open={confirmRevoke}
        title="Encerrar outras sessões?"
        confirmLabel="Encerrar"
        busy={revoking}
        onConfirm={revokeOthers}
        onCancel={() => setConfirmRevoke(false)}
      >
        Todos os outros navegadores e computadores em que você está conectado precisarão entrar de novo. Esta sessão continua.
      </ConfirmDialog>
    </div>
  );
}
