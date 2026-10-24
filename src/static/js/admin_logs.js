// O log contém texto controlado por qualquer pessoa — inclusive anônimos (ex: o username
// digitado numa tentativa de login falha). Por isso tudo é inserido com textContent:
// um "username" como <script>...</script> aparece como texto, nunca é executado.

const limitSelect = document.getElementById("logs-limit");
const levelSelect = document.getElementById("logs-level");
const searchInput = document.getElementById("logs-search");
const list = document.getElementById("logs-list");
const summary = document.getElementById("logs-summary");
const errorEl = document.getElementById("logs-error");

let entries = [];

// Formato gravado pelo logging_config.py: "2026-10-24 12:34:04,608 INFO mensagem..."
const LINE_PATTERN = /^(\S+ \S+) (\w+) (.*)$/;

function parseLine(line) {
    const match = LINE_PATTERN.exec(line);
    if (!match) {
        return { timestamp: "", level: "", message: line };
    }
    return { timestamp: match[1], level: match[2], message: match[3] };
}

function render() {
    const level = levelSelect.value;
    const search = searchInput.value.trim().toLowerCase();

    const visible = entries.filter(
        (e) => (!level || e.level === level) && (!search || e.message.toLowerCase().includes(search)),
    );

    list.replaceChildren();
    // Mais recentes primeiro: é o que o admin quer ver ao abrir a página.
    for (const entry of [...visible].reverse()) {
        const item = document.createElement("li");
        item.className = `log-line log-line--${entry.level.toLowerCase() || "other"}`;

        const time = document.createElement("span");
        time.className = "log-line__time";
        time.textContent = entry.timestamp;

        const levelBadge = document.createElement("span");
        levelBadge.className = "log-line__level";
        levelBadge.textContent = entry.level;

        const message = document.createElement("span");
        message.className = "log-line__message";
        message.textContent = entry.message;

        item.append(time, levelBadge, message);
        list.append(item);
    }

    summary.textContent = `Mostrando ${visible.length} de ${entries.length} linhas carregadas.`;
}

async function loadLogs() {
    errorEl.hidden = true;
    try {
        const data = await apiRequest(`/logs/app?limit=${encodeURIComponent(limitSelect.value)}`);
        entries = data.lines.map(parseLine);
        render();
        document.getElementById("logs-updated").textContent =
            `Atualizado às ${new Date().toLocaleTimeString("pt-BR")}`;
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.hidden = false;
    }
}

limitSelect.addEventListener("change", loadLogs);
levelSelect.addEventListener("change", render);
searchInput.addEventListener("input", render);
document.getElementById("logs-refresh").addEventListener("click", loadLogs);

loadLogs();
