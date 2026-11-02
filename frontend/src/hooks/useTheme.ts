import { useCallback, useSyncExternalStore } from "react";

export type Theme = "light" | "dark";

function subscribe(callback: () => void): () => void {
  const observer = new MutationObserver(callback);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

const getTheme = (): Theme => (document.documentElement.classList.contains("dark") ? "dark" : "light");

/** O tema vive na classe `dark` do <html> (mesma chave de localStorage das páginas atuais). */
export function useTheme() {
  const theme = useSyncExternalStore(subscribe, getTheme);

  const toggle = useCallback(() => {
    const next: Theme = getTheme() === "dark" ? "light" : "dark";
    document.documentElement.classList.toggle("dark", next === "dark");
    try {
      localStorage.setItem("datavision-theme", next);
    } catch {
      // Sem armazenamento: vale só até recarregar.
    }
  }, []);

  return { theme, toggle };
}
