document.getElementById("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const errorEl = document.getElementById("login-error");
    errorEl.hidden = true;

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    try {
        await apiRequest("/login", {
            method: "POST",
            body: JSON.stringify({ username, password }),
        });
        window.location.href = "/";
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.hidden = false;
    }
});
