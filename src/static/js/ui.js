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
