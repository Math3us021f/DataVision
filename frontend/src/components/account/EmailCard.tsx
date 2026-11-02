import { Mail } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { buttonStyles } from "@/components/ui/button";
import { Card, CardSubtitle, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";

type Step = "view" | "form" | "code";

/** E-mail de verificação da própria conta: trocar exige a senha atual e um código enviado ao endereço NOVO. */
export function EmailCard({ emailMasked, onChanged }: { emailMasked: string | null; onChanged: () => void }) {
  const toast = useToast();
  const [step, setStep] = useState<Step>("view");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [hint, setHint] = useState("");
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = window.setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => window.clearTimeout(id);
  }, [cooldown]);

  function reset() {
    setStep("view");
    setEmail("");
    setPassword("");
    setCode("");
    setError(null);
  }

  async function request(event?: FormEvent) {
    event?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ email_hint: string; resend_in: number }>("/me/email/request", {
        method: "POST",
        body: JSON.stringify({ email, current_password: password }),
      });
      setHint(res.email_hint);
      setCooldown(res.resend_in);
      setCode("");
      setStep("code");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível enviar o código.");
    } finally {
      setBusy(false);
    }
  }

  async function confirm(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/me/email/confirm", { method: "POST", body: JSON.stringify({ code }) });
      toast("E-mail confirmado e salvo.");
      reset();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível confirmar o código.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card id="email-card" className="p-5">
      <div className="flex items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent">
          <Mail className="size-[18px]" />
        </span>
        <div className="min-w-0">
          <CardTitle>E-mail de verificação</CardTitle>
          <CardSubtitle>
            Quem tem e-mail cadastrado recebe um código a cada login. O endereço é usado só para isso e aparece sempre mascarado.
          </CardSubtitle>
        </div>
      </div>

      {step === "view" && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p id="email-current" className={emailMasked ? "text-sm font-medium" : "text-sm text-muted"}>
            {emailMasked ?? "Nenhum e-mail cadastrado — o login pede só a senha."}
          </p>
          <button type="button" id="email-open" onClick={() => setStep("form")} className={buttonStyles({ variant: "secondary", size: "sm" })}>
            {emailMasked ? "Alterar e-mail" : "Cadastrar e-mail"}
          </button>
        </div>
      )}

      {step === "form" && (
        <form onSubmit={request} className="mt-4 flex flex-col gap-3">
          <Field label="Novo e-mail" htmlFor="email-new">
            <Input id="email-new" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
          </Field>
          <Field label="Senha atual (para confirmar que é você)" htmlFor="email-password">
            <Input id="email-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </Field>
          {error && (
            <p id="email-error" role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={reset} className={buttonStyles({ variant: "secondary", size: "sm" })}>
              Cancelar
            </button>
            <button type="submit" id="email-send" disabled={busy} className={buttonStyles({ variant: "primary", size: "sm" })}>
              Enviar código
            </button>
          </div>
        </form>
      )}

      {step === "code" && (
        <form onSubmit={confirm} className="mt-4 flex flex-col gap-3">
          <p className="text-sm text-muted">
            Enviamos um código de 6 dígitos para <strong className="text-foreground">{hint}</strong>. Ele vale por 10 minutos.
          </p>
          <Field label="Código" htmlFor="email-code">
            <Input
              id="email-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={12}
              placeholder="000000"
              className="tracking-[0.3em]"
              required
              autoFocus
            />
          </Field>
          {error && (
            <p id="email-error" role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm">
              {error}
            </p>
          )}
          <div className="flex flex-wrap justify-between gap-2">
            <button type="button" id="email-resend" disabled={cooldown > 0 || busy} onClick={() => request()} className={buttonStyles({ variant: "ghost", size: "sm" })}>
              {cooldown > 0 ? `Reenviar em ${cooldown} s` : "Reenviar código"}
            </button>
            <div className="flex gap-2">
              <button type="button" onClick={reset} className={buttonStyles({ variant: "secondary", size: "sm" })}>
                Cancelar
              </button>
              <button type="submit" id="email-confirm" disabled={busy || code.trim().length < 6} className={buttonStyles({ variant: "primary", size: "sm" })}>
                Confirmar
              </button>
            </div>
          </div>
        </form>
      )}
    </Card>
  );
}
