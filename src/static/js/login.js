const form = document.getElementById("login-form");
const errorEl = document.getElementById("login-error");
const submitButton = document.getElementById("login-submit");
const passwordInput = document.getElementById("password");
const toggleButton = document.getElementById("password-toggle");

toggleButton.addEventListener("click", () => {
    const showing = passwordInput.type === "text";
    passwordInput.type = showing ? "password" : "text";
    const label = showing ? "Mostrar senha" : "Ocultar senha";
    toggleButton.setAttribute("aria-label", label);
    toggleButton.title = label;
    toggleButton.classList.toggle("is-active", !showing);
});

function showError(message) {
    errorEl.textContent = message;
    errorEl.hidden = false;
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.hidden = true;

    const username = document.getElementById("username").value.trim();
    const password = passwordInput.value;

    if (!username || !password) {
        showError("Preencha usuário e senha.");
        return;
    }

    submitButton.disabled = true;
    submitButton.replaceChildren(Object.assign(document.createElement("span"), { className: "spinner spinner--light" }), " Entrando...");

    try {
        await apiRequest("/login", {
            method: "POST",
            body: JSON.stringify({ username, password }),
        });
        window.location.href = "/";
    } catch (err) {
        showError(err.message);
        submitButton.disabled = false;
        submitButton.textContent = "Entrar";
        passwordInput.select();
    }
});
