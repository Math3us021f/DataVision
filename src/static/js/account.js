const passwordForm = document.getElementById("password-form");
const passwordError = document.getElementById("password-error");
const passwordSubmit = document.getElementById("password-submit");

passwordForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    passwordError.hidden = true;

    const currentPassword = document.getElementById("current-password").value;
    const newPassword = document.getElementById("new-password").value;
    const confirmPassword = document.getElementById("confirm-password").value;

    // Conferência só de usabilidade; as regras de verdade (tamanho, senha atual) ficam no servidor.
    if (newPassword !== confirmPassword) {
        passwordError.textContent = "A confirmação não confere com a nova senha.";
        passwordError.hidden = false;
        return;
    }

    passwordSubmit.disabled = true;
    try {
        await apiRequest("/me/password", {
            method: "PUT",
            body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
        });
        passwordForm.reset();
        showToast("Senha alterada. Outras sessões foram encerradas.", "success");
    } catch (err) {
        passwordError.textContent = err.message;
        passwordError.hidden = false;
    } finally {
        passwordSubmit.disabled = false;
    }
});
