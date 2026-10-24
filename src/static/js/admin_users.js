// Todo texto vindo da API é inserido com textContent (nunca innerHTML),
// para que um nome de usuário malicioso apareça como texto e não seja executado (XSS).

const tableBody = document.getElementById("users-table-body");
const usersError = document.getElementById("users-error");

function cell(text) {
    const td = document.createElement("td");
    td.textContent = text;
    return td;
}

function renderUsers(users) {
    tableBody.replaceChildren();

    for (const user of users) {
        const row = document.createElement("tr");
        row.append(
            cell(user.id),
            cell(user.username),
            cell(user.is_admin ? "Administrador" : "Usuário"),
            cell(user.is_active ? "Ativo" : "Inativo"),
        );

        const actionCell = document.createElement("td");
        const button = document.createElement("button");
        button.className = "button--small" + (user.is_active ? " button--danger" : "");
        button.textContent = user.is_active ? "Desativar" : "Ativar";
        // O backend já impede o admin de se desativar; aqui só evitamos o clique inútil.
        button.disabled = user.username === window.CURRENT_USERNAME;
        button.addEventListener("click", () => toggleActive(user));
        actionCell.append(button);
        row.append(actionCell);

        tableBody.append(row);
    }
}

async function loadUsers() {
    usersError.hidden = true;
    try {
        const users = await apiRequest("/users");
        renderUsers(users);
    } catch (err) {
        usersError.textContent = err.message;
        usersError.hidden = false;
    }
}

async function toggleActive(user) {
    try {
        await apiRequest(`/users/${user.id}`, {
            method: "PATCH",
            body: JSON.stringify({ is_active: !user.is_active }),
        });
        await loadUsers();
    } catch (err) {
        usersError.textContent = err.message;
        usersError.hidden = false;
    }
}

document.getElementById("create-user-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = document.getElementById("create-user-message");
    message.hidden = true;

    const usernameInput = document.getElementById("new-username");
    const passwordInput = document.getElementById("new-password");
    const isAdminInput = document.getElementById("new-is-admin");

    try {
        const created = await apiRequest("/users", {
            method: "POST",
            body: JSON.stringify({
                username: usernameInput.value,
                password: passwordInput.value,
                is_admin: isAdminInput.checked,
            }),
        });
        message.className = "message message--success";
        message.textContent = `Usuário "${created.username}" criado.`;
        event.target.reset();
        await loadUsers();
    } catch (err) {
        message.className = "message message--error";
        message.textContent = err.message;
    }
    message.hidden = false;
});

loadUsers();
