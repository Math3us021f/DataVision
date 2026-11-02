import { useCallback, useEffect, useRef, useState } from "react";

import { buttonStyles } from "@/components/ui/button";
import { Modal } from "@/components/ui/dialog";
import { api } from "@/lib/api";

/** Chave compartilhada entre abas: atividade em uma aba vale para todas (senão uma aba parada derrubaria a sessão). */
const SHARED_KEY = "datavision-last-activity";
const WARNING_SECONDS = 60;
const PING_EVERY_MS = 20_000;
const ACTIVITY_EVENTS = ["pointerdown", "pointermove", "keydown", "wheel", "scroll", "touchstart"] as const;

const readShared = (): number => {
  try {
    return Number(localStorage.getItem(SHARED_KEY)) || 0;
  } catch {
    return 0;
  }
};
const writeShared = (time: number) => {
  try {
    localStorage.setItem(SHARED_KEY, String(time));
  } catch {
    // Sem localStorage (janela privativa etc.): cada aba cuida só de si.
  }
};

/**
 * Avisa antes de a sessão cair por inatividade e desconecta se a pessoa não confirmar.
 * Quem encerra a sessão de verdade é o servidor (ele conta o tempo e recusa o cookie vencido);
 * aqui só se avisa, e se mantém o servidor informado de que a pessoa está ativa.
 */
export function IdleGuard({ idleSeconds }: { idleSeconds: number }) {
  const idleMs = idleSeconds * 1000;
  const warningMs = Math.min(WARNING_SECONDS * 1000, idleMs / 2);
  const lastActivity = useRef(Date.now());
  const lastPing = useRef(Date.now());
  const warningOpen = useRef(false);
  const leaving = useRef(false);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);

  const touch = useCallback((now: number) => {
    lastActivity.current = now;
    writeShared(now);
  }, []);

  const logout = useCallback(() => {
    if (leaving.current) return;
    leaving.current = true;
    api("/logout", { method: "POST" })
      .catch(() => undefined)
      .finally(() => {
        window.location.href = "/login?expired=idle";
      });
  }, []);

  const keepAlive = useCallback(() => {
    // Qualquer chamada feita pela pessoa renova o prazo no servidor; se já tiver vencido, a api() leva ao login.
    api("/me").catch(() => undefined);
  }, []);

  const confirm = useCallback(() => {
    const now = Date.now();
    warningOpen.current = false;
    setSecondsLeft(null);
    touch(now);
    lastPing.current = now;
    keepAlive();
  }, [touch, keepAlive]);

  useEffect(() => {
    touch(Date.now()); // abrir a tela já é atividade (a chamada a /me que a trouxe renovou o servidor)

    const onActivity = () => {
      if (warningOpen.current) return; // com o aviso aberto, só os botões respondem
      const now = Date.now();
      if (now - lastActivity.current >= 1000) touch(now);
      if (now - lastPing.current >= PING_EVERY_MS) {
        lastPing.current = now;
        keepAlive();
      }
    };
    for (const name of ACTIVITY_EVENTS) window.addEventListener(name, onActivity, { passive: true, capture: true });

    const timer = window.setInterval(() => {
      const idle = Date.now() - Math.max(lastActivity.current, readShared());
      if (idle >= idleMs) {
        logout();
      } else if (idle >= idleMs - warningMs) {
        warningOpen.current = true;
        setSecondsLeft(Math.ceil((idleMs - idle) / 1000));
      } else if (warningOpen.current) {
        warningOpen.current = false; // outra aba teve atividade: não precisa mais avisar
        setSecondsLeft(null);
      }
    }, 1000);

    return () => {
      for (const name of ACTIVITY_EVENTS) window.removeEventListener(name, onActivity, { capture: true });
      window.clearInterval(timer);
    };
  }, [idleMs, warningMs, touch, keepAlive, logout]);

  return (
    <Modal
      open={secondsLeft !== null}
      onClose={() => undefined}
      dismissible={false}
      title="Você ainda está aí?"
      footer={
        <>
          <button type="button" id="idle-logout" onClick={logout} className={buttonStyles({ variant: "secondary" })}>
            Sair agora
          </button>
          <button type="button" id="idle-continue" onClick={confirm} className={buttonStyles({ variant: "primary" })}>
            Continuar conectado
          </button>
        </>
      }
    >
      Sua sessão vai expirar por inatividade em <strong id="idle-seconds" className="tabular-nums text-foreground">{secondsLeft ?? 0}</strong> s.
      Se não confirmar, você será desconectado.
    </Modal>
  );
}
