// Componentes de interface compartilhados por todas as páginas do layout com barra lateral.

function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast--${type}`;
    toast.setAttribute("role", "status");
    toast.textContent = message;
    container.append(toast);

    setTimeout(() => {
        toast.classList.add("toast--leaving");
        toast.addEventListener("animationend", () => toast.remove(), { once: true });
    }, 3500);
}

// Retorna uma Promise<boolean>: true se o usuário confirmou.
function confirmAction({ title, message, confirmLabel = "Confirmar" }) {
    const dialog = document.getElementById("confirm-dialog");
    document.getElementById("confirm-title").textContent = title;
    document.getElementById("confirm-message").textContent = message;
    const okButton = document.getElementById("confirm-ok");
    const cancelButton = document.getElementById("confirm-cancel");
    okButton.textContent = confirmLabel;

    return new Promise((resolve) => {
        const finish = (result) => {
            okButton.removeEventListener("click", onOk);
            cancelButton.removeEventListener("click", onCancel);
            dialog.removeEventListener("cancel", onCancel);
            dialog.close();
            resolve(result);
        };
        const onOk = () => finish(true);
        const onCancel = (event) => {
            event?.preventDefault?.();
            finish(false);
        };

        okButton.addEventListener("click", onOk);
        cancelButton.addEventListener("click", onCancel);
        dialog.addEventListener("cancel", onCancel);  // tecla Esc
        dialog.showModal();
        cancelButton.focus();
    });
}

// Iniciais para o avatar (só a primeira letra, como texto).
function initialOf(name) {
    return (name || "?").trim().charAt(0).toUpperCase();
}

// ---------- Estados de tela ----------

// Desenha um estado padronizado (vazio ou erro) dentro de `container`.
// Textos entram com textContent: podem conter dados vindos da API.
function renderState(container, { kind = "empty", title, message = "" }) {
    const state = document.createElement("div");
    state.className = `state state--${kind}`;
    state.setAttribute("role", kind === "error" ? "alert" : "status");

    const iconWrap = document.createElement("div");
    iconWrap.className = "state__icon";
    const template = document.getElementById(`state-icon-${kind}`);
    if (template) iconWrap.append(template.content.cloneNode(true));

    const titleEl = document.createElement("div");
    titleEl.className = "state__title";
    titleEl.textContent = title;

    const messageEl = document.createElement("p");
    messageEl.className = "state__message";
    messageEl.textContent = message;

    state.append(iconWrap, titleEl, messageEl);
    container.replaceChildren(state);
    container.hidden = false;
}

// ---------- Painel lateral (drawer) ----------

function openDrawer(id) {
    const drawer = document.getElementById(id);
    drawer.showModal();
    const firstField = drawer.querySelector("input, select, textarea");
    if (firstField) firstField.focus();
}

function closeDrawer(id) {
    document.getElementById(id).close();
}

// Botões com data-drawer-open="id" abrem; data-drawer-close fecham o painel em que estão.
document.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-drawer-open]");
    if (opener) openDrawer(opener.dataset.drawerOpen);

    const closer = event.target.closest("[data-drawer-close]");
    if (closer) closer.closest("dialog").close();
});

// Clique no fundo escurecido (fora do painel) também fecha.
document.querySelectorAll("dialog.drawer").forEach((drawer) => {
    drawer.addEventListener("click", (event) => {
        if (event.target === drawer) drawer.close();
    });
});

// ---------- Tema claro/escuro ----------

const themeToggle = document.getElementById("theme-toggle");
if (themeToggle) {
    themeToggle.addEventListener("click", () => {
        const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
        document.documentElement.setAttribute("data-theme", next);
        try {
            localStorage.setItem("datavision-theme", next);
        } catch (e) {
            // Sem armazenamento (ex: navegação privada): o tema vale só até recarregar.
        }
    });
}

// ---------- Menu no celular ----------

const app = document.getElementById("app");
const menuToggle = document.getElementById("menu-toggle");
if (app && menuToggle) {
    const setMenu = (open) => {
        app.classList.toggle("menu-open", open);
        menuToggle.setAttribute("aria-expanded", String(open));
    };
    menuToggle.addEventListener("click", () => setMenu(!app.classList.contains("menu-open")));
    document.getElementById("sidebar-backdrop").addEventListener("click", () => setMenu(false));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") setMenu(false);
    });
}

// ---------- Sair ----------

const logoutButton = document.getElementById("logout-button");
if (logoutButton) {
    logoutButton.addEventListener("click", async () => {
        try {
            await apiRequest("/logout", { method: "POST" });
        } finally {
            window.location.href = "/login";
        }
    });
}
