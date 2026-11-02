import { useCallback, useState } from "react";

const KEY = "datavision-sidebar";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(KEY) === "collapsed";
  } catch {
    return false;
  }
}

/** Menu lateral recolhido ou aberto; a escolha é lembrada (mesma chave das páginas atuais). */
export function useSidebar() {
  const [collapsed, setCollapsed] = useState(readCollapsed);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(KEY, next ? "collapsed" : "expanded");
      } catch {
        // Sem armazenamento: vale só até recarregar.
      }
      return next;
    });
  }, []);

  return { collapsed, toggle };
}
