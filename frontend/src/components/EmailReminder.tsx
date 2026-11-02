import { Mail, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

const DISMISSED_KEY = "datavision-email-reminder-dismissed";

const wasDismissed = (): boolean => {
  try {
    return sessionStorage.getItem(DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
};

/** Aviso flutuante que lembra quem não tem e-mail cadastrado de ativar a verificação em dois passos (some até o próximo login se dispensado). */
export function EmailReminder() {
  const [hidden, setHidden] = useState(wasDismissed);
  if (hidden) return null;

  return (
    // Flutua sobre a tela em vez de ocupar espaço no layout (a Home foi desenhada para caber numa tela sem rolagem).
    <div
      id="email-reminder"
      role="status"
      className="fixed bottom-4 left-1/2 z-30 flex w-[min(92vw,520px)] -translate-x-1/2 items-center gap-3 rounded-xl border border-accent/40 bg-surface px-4 py-2.5 text-sm shadow-card"
    >
      <Mail className="size-4 shrink-0 text-accent" />
      <p className="min-w-0 flex-1">
        Cadastre seu e-mail para ativar a verificação em dois passos no login.{" "}
        <Link to="/account?aba=seguranca" className="font-medium text-accent underline-offset-4 hover:underline">
          Cadastrar agora
        </Link>
      </p>
      <button
        type="button"
        aria-label="Dispensar aviso"
        onClick={() => {
          try {
            sessionStorage.setItem(DISMISSED_KEY, "1");
          } catch {
            // Sem sessionStorage: o aviso some só até recarregar a página.
          }
          setHidden(true);
        }}
        className="grid size-7 shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-foreground"
      >
        <X className="size-4" />
      </button>
    </div>
  );
}
