// Nomes de arquivo e conteúdo (no perfilamento) vêm de dados do usuário — sempre textContent.

const ALLOWED_EXTENSIONS = [".csv", ".xlsx"];
const MAX_BYTES = 10_000_000;

function formatBytes(bytes) {
    const units = ["B", "KB", "MB", "GB"];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
        value /= 1024;
        unit += 1;
    }
    return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

// ---------- Upload (arrastar e soltar, com barra de progresso) ----------

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const queue = document.getElementById("upload-queue");
const uploadError = document.getElementById("upload-error");

function openPicker() {
    fileInput.value = "";
    fileInput.click();
}
dropzone.addEventListener("click", openPicker);
dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openPicker(); }
});

["dragenter", "dragover"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.add("dropzone--active"); }),
);
["dragleave", "drop"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.remove("dropzone--active"); }),
);
dropzone.addEventListener("drop", (e) => {
    for (const file of e.dataTransfer.files) startUpload(file);
});
fileInput.addEventListener("change", () => {
    for (const file of fileInput.files) startUpload(file);
});

function startUpload(file) {
    uploadError.hidden = true;

    // Checagem só de usabilidade (feedback imediato); quem valida de verdade é o servidor.
    const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
        uploadError.textContent = `"${file.name}": formato não permitido (use .csv ou .xlsx).`;
        uploadError.hidden = false;
        return;
    }
    if (file.size > MAX_BYTES) {
        uploadError.textContent = `"${file.name}": arquivo maior que 10 MB.`;
        uploadError.hidden = false;
        return;
    }

    const item = el("li", "upload-item");
    const name = el("span", "upload-item__name", file.name);
    const bar = el("div", "bar upload-item__bar");
    const fill = el("div", "bar__fill");
    bar.append(fill);
    const status = el("span", "upload-item__status", "Enviando…");
    item.append(name, bar, status);
    queue.prepend(item);

    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/datasets/upload");
    xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) fill.style.width = `${Math.round((e.loaded / e.total) * 100)}%`;
    });
    xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
            fill.style.width = "100%";
            status.textContent = "Concluído";
            item.classList.add("upload-item--done");
            showToast(`"${file.name}" enviado.`, "success");
            setTimeout(() => item.remove(), 2500);
            loadDatasets();
        } else {
            let message = `Erro ${xhr.status}`;
            try { message = JSON.parse(xhr.responseText).detail || message; } catch { /* corpo não era JSON */ }
            status.textContent = message;
            item.classList.add("upload-item--error");
        }
    });
    xhr.addEventListener("error", () => {
        status.textContent = "Falha de conexão";
        item.classList.add("upload-item--error");
    });
    xhr.send(formData);
}

// ---------- Listagem ----------

const tableBody = document.getElementById("datasets-table-body");
const stateBox = document.getElementById("datasets-state");

function renderDatasets(datasets) {
    tableBody.replaceChildren();
    stateBox.hidden = true;

    if (datasets.length === 0) {
        renderState(stateBox, {
            kind: "empty",
            title: "Nenhum dataset enviado",
            message: "Envie um arquivo CSV ou Excel acima para começar.",
        });
        return;
    }

    for (const dataset of datasets) {
        const row = el("tr");
        row.append(el("td", "", dataset.original_name), el("td", "", dataset.format), el("td", "", formatBytes(dataset.size_bytes)));

        const actions = el("td", "actions");
        const group = el("div", "actions-group");

        const profileButton = el("button", "button--small button--secondary", "Perfil");
        profileButton.type = "button";
        profileButton.addEventListener("click", () => openProfile(dataset));

        const deleteButton = el("button", "icon-button icon-button--danger");
        deleteButton.type = "button";
        deleteButton.setAttribute("aria-label", `Excluir ${dataset.original_name}`);
        deleteButton.append(document.getElementById("icon-trash")?.content.cloneNode(true) ?? document.createTextNode("Excluir"));
        deleteButton.addEventListener("click", () => deleteDataset(dataset));

        group.append(profileButton, deleteButton);
        actions.append(group);
        row.append(actions);
        tableBody.append(row);
    }
}

async function loadDatasets() {
    try {
        renderDatasets(await apiRequest("/datasets"));
    } catch (err) {
        tableBody.replaceChildren();
        renderState(stateBox, { kind: "error", title: "Não foi possível carregar os datasets", message: err.message });
    }
}

async function deleteDataset(dataset) {
    const confirmed = await confirmAction({
        title: "Excluir dataset?",
        message: `"${dataset.original_name}" e seu perfilamento serão apagados, junto com o arquivo armazenado. Não dá para desfazer.`,
        confirmLabel: "Excluir",
    });
    if (!confirmed) return;

    try {
        await apiRequest(`/datasets/${dataset.id}`, { method: "DELETE" });
        showToast(`"${dataset.original_name}" excluído.`, "success");
        await loadDatasets();
    } catch (err) {
        showToast(err.message, "error");
    }
}

// ---------- Perfilamento ----------

const TYPE_LABELS = { integer: "Inteiro", float: "Decimal", text: "Texto", boolean: "Booleano", datetime: "Data/hora" };

function profileRow(label, value) {
    const row = el("div", "profile-stat");
    row.append(el("span", "muted", label), el("span", "profile-stat__value", value));
    return row;
}

function columnCard(column, totalRows) {
    const card = el("div", "column-card");
    card.append(el("div", "column-card__name", column.column_name), el("span", "badge badge--neutral badge--plain", TYPE_LABELS[column.inferred_type] ?? column.inferred_type));

    const nullPercent = totalRows ? (column.null_count / totalRows) * 100 : 0;
    const nullLine = el("div", "column-card__metric");
    nullLine.append(el("span", "muted", `Ausentes: ${column.null_count} (${nullPercent.toFixed(1)}%)`));
    const nullBar = el("div", "bar");
    const nullFill = el("div", `bar__fill${nullPercent >= 50 ? " bar__fill--danger" : nullPercent >= 15 ? " bar__fill--warning" : ""}`);
    nullFill.style.width = `${Math.min(nullPercent, 100)}%`;
    nullBar.append(nullFill);
    nullLine.append(nullBar);

    const distinctPercent = totalRows ? (column.distinct_count / totalRows) * 100 : 0;
    const distinctLine = el("div", "column-card__metric");
    distinctLine.append(el("span", "muted", `Valores distintos: ${column.distinct_count} (${distinctPercent.toFixed(1)}%)`));
    const distinctBar = el("div", "bar");
    const distinctFill = el("div", "bar__fill");
    distinctFill.style.width = `${Math.min(distinctPercent, 100)}%`;
    distinctBar.append(distinctFill);
    distinctLine.append(distinctBar);

    card.append(nullLine, distinctLine);

    if (column.min_value !== null) {
        const stats = el("div", "column-card__stats");
        const formatNumber = (n) => Number.isInteger(n) ? String(n) : n.toFixed(2);
        stats.append(
            statPill("Mín.", formatNumber(column.min_value)),
            statPill("Máx.", formatNumber(column.max_value)),
            statPill("Média", formatNumber(column.mean_value)),
            statPill("Mediana", formatNumber(column.median_value)),
        );
        card.append(stats);
    }

    if (column.top_values && column.top_values.length > 0) {
        card.append(topValuesList(column.top_values));
    }

    if (column.histogram || (column.top_values && column.top_values.length > 0)) {
        // Precisa de um wrapper com altura fixa: dentro de um painel com rolagem, um <canvas>
        // "responsivo" sem um ancestral de tamanho definido acaba medindo a altura errada
        // (o Chart.js tentou usar a altura do scroll inteiro, não a da tela visível).
        const wrap = el("div", "column-chart-wrap");
        const canvas = document.createElement("canvas");
        canvas.id = `chart-${chartCounter++}`;
        wrap.append(canvas);
        card.append(wrap);
        pendingCharts.push({ canvas, column });
    }

    return card;
}

// Canvas só pode virar gráfico depois de estar no DOM — por isso a criação real do
// Chart.js fica para depois do card inteiro já ter sido inserido na página (ver renderProfile).
let chartCounter = 0;
let pendingCharts = [];
let activeCharts = [];

function destroyActiveCharts() {
    for (const chart of activeCharts) chart.destroy();
    activeCharts = [];
}

function formatBinLabel(start, end) {
    const round = (n) => (Number.isInteger(n) ? n : Math.round(n * 100) / 100);
    return `${round(start)}–${round(end)}`;
}

function buildChart({ canvas, column }) {
    const styles = getComputedStyle(document.documentElement);
    const accent = styles.getPropertyValue("--accent").trim();
    const textColor = styles.getPropertyValue("--text-muted").trim();
    const gridColor = styles.getPropertyValue("--border").trim();

    const common = {
        plugins: { legend: { display: false } },
        scales: {
            x: { ticks: { color: textColor, maxRotation: 0, autoSkip: true }, grid: { display: false } },
            y: { ticks: { color: textColor, precision: 0 }, grid: { color: gridColor } },
        },
    };

    if (column.histogram) {
        const { bin_edges, counts } = column.histogram;
        const labels = counts.map((_, i) => formatBinLabel(bin_edges[i], bin_edges[i + 1]));
        return new Chart(canvas, {
            type: "bar",
            data: { labels, datasets: [{ data: counts, backgroundColor: accent, borderRadius: 3 }] },
            options: { ...common, responsive: true, maintainAspectRatio: false },
        });
    }

    // Coluna de texto: barras horizontais com os valores mais frequentes.
    const labels = column.top_values.map((t) => t.value);
    const counts = column.top_values.map((t) => t.count);
    return new Chart(canvas, {
        type: "bar",
        data: { labels, datasets: [{ data: counts, backgroundColor: accent, borderRadius: 3 }] },
        options: { ...common, indexAxis: "y", responsive: true, maintainAspectRatio: false },
    });
}

function topValuesList(topValues) {
    const wrapper = el("div", "top-values");
    wrapper.append(el("div", "top-values__title", "Valores mais frequentes"));

    const maxCount = Math.max(...topValues.map((t) => t.count));
    for (const { value, count } of topValues) {
        const row = el("div", "top-value-row");
        const label = el("span", "top-value-row__label", value);
        const bar = el("div", "bar top-value-row__bar");
        const fill = el("div", "bar__fill");
        fill.style.width = `${(count / maxCount) * 100}%`;
        bar.append(fill);
        const countEl = el("span", "top-value-row__count", String(count));
        row.append(label, bar, countEl);
        wrapper.append(row);
    }
    return wrapper;
}

function statPill(label, value) {
    const pill = el("div", "stat-pill");
    pill.append(el("span", "stat-pill__label", label), el("span", "stat-pill__value", value));
    return pill;
}

function renderProfile(profile) {
    const body = document.getElementById("profile-body");
    destroyActiveCharts();
    pendingCharts = [];
    body.replaceChildren();

    const summary = el("div", "profile-summary");
    summary.append(
        profileRow("Linhas", profile.row_count),
        profileRow("Linhas duplicadas", profile.duplicate_row_count),
        profileRow("Colunas", profile.columns.length),
    );
    body.append(summary);

    const grid = el("div", "column-grid");
    for (const column of profile.columns) grid.append(columnCard(column, profile.row_count));
    body.append(grid);

    // Só agora os canvases estão de verdade na página — o Chart.js precisa disso para medir e desenhar.
    for (const pending of pendingCharts) activeCharts.push(buildChart(pending));
    pendingCharts = [];
}

function renderSample(sample) {
    const container = document.getElementById("profile-sample");
    container.replaceChildren();

    const header = el("div", "sample-header");
    header.append(
        el("h3", "sample-header__title", "Amostra dos dados"),
        el("span", "muted", `${sample.sample_size} de ${sample.total_rows} linha(s)`),
    );
    container.append(header);

    const wrapper = el("div", "table-wrapper sample-table-wrapper");
    const table = el("table", "table sample-table");
    const thead = el("thead");
    const headRow = el("tr");
    for (const columnName of sample.columns) headRow.append(el("th", "", columnName));
    thead.append(headRow);

    const tbody = el("tbody");
    for (const row of sample.rows) {
        const tr = el("tr");
        for (const cell of row) {
            tr.append(el("td", cell === null ? "sample-table__null" : "", cell === null ? "—" : cell));
        }
        tbody.append(tr);
    }

    table.append(thead, tbody);
    wrapper.append(table);
    container.append(wrapper);
}

let activeDataset = null;

async function openProfile(dataset) {
    activeDataset = dataset;
    destroyActiveCharts();
    document.getElementById("profile-title").textContent = "Perfilamento";
    document.getElementById("profile-subtitle").textContent = dataset.original_name;
    const body = document.getElementById("profile-body");
    const sampleContainer = document.getElementById("profile-sample");
    body.replaceChildren(el("p", "muted", "Carregando…"));
    sampleContainer.replaceChildren();
    document.getElementById("profile-recalculate").textContent = "Recalcular";
    openDrawer("profile-drawer");

    apiRequest(`/datasets/${dataset.id}/sample`)
        .then(renderSample)
        .catch((err) => renderState(sampleContainer, { kind: "error", title: "Não foi possível carregar a amostra", message: err.message }));

    try {
        renderProfile(await apiRequest(`/datasets/${dataset.id}/profile`));
    } catch (err) {
        if (err.status === 404) {
            body.replaceChildren();
            renderState(body, {
                kind: "empty",
                title: "Ainda não perfilado",
                message: "Clique em \"Calcular perfil\" para analisar as colunas deste arquivo.",
            });
            document.getElementById("profile-recalculate").textContent = "Calcular perfil";
        } else {
            body.replaceChildren();
            renderState(body, { kind: "error", title: "Não foi possível carregar o perfil", message: err.message });
        }
    }
}

document.getElementById("profile-recalculate").addEventListener("click", async () => {
    if (!activeDataset) return;
    const body = document.getElementById("profile-body");
    body.replaceChildren(el("p", "muted", "Calculando…"));
    try {
        renderProfile(await apiRequest(`/datasets/${activeDataset.id}/profile`, { method: "POST" }));
        document.getElementById("profile-recalculate").textContent = "Recalcular";
        showToast("Perfil calculado.", "success");
    } catch (err) {
        body.replaceChildren();
        renderState(body, { kind: "error", title: "Não foi possível calcular o perfil", message: err.message });
    }
});

loadDatasets();
