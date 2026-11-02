// Construtor do dashboard (JS puro). O estado vive só na página (ainda não há "salvar").
// Todo texto vindo da API ou do arquivo do usuário entra via textContent, nunca innerHTML.

const DATASET_ID = window.DATASET_ID;
const DEBOUNCE_MS = 350;
const FILTER_DEBOUNCE_MS = 450;

const AGG_LABELS = {
    sum: "Soma", mean: "Média", count: "Contagem", min: "Mínimo", max: "Máximo", count_distinct: "Valores distintos",
};
const CHART_LABELS = { bar: "Barras", line: "Linha", pie: "Pizza", kpi: "Indicador (KPI)" };
const GRAIN_LABELS = { day: "Dia", month: "Mês", year: "Ano" };
const OP_LABELS = {
    eq: "é igual a", ne: "é diferente de", gt: ">", gte: "≥", lt: "<", lte: "≤",
    contains: "contém", in: "é um de (separe por vírgula)",
};
const NUMERIC = new Set(["integer", "float"]);
const NUMERIC_AGGS = ["sum", "mean", "count", "min", "max", "count_distinct"];
const OTHER_AGGS = ["count", "count_distinct"];
const OPS_BY_TYPE = {
    text: ["eq", "ne", "contains", "in"],
    number: ["eq", "ne", "gt", "gte", "lt", "lte", "in"],
    datetime: ["eq", "ne", "gt", "gte", "lt", "lte"],
    boolean: ["eq", "ne"],
};

const widgetsBox = document.getElementById("widgets");
const stateBox = document.getElementById("dashboard-state");
const filtersCard = document.getElementById("filters-card");
const filtersList = document.getElementById("filters-list");
const actionsBar = document.getElementById("dashboard-actions");

const state = { columns: [], widgets: [], filters: [] };
let nextId = 1;

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function option(value, label) {
    const node = el("option", "", label);
    node.value = value;
    return node;
}

function typeOf(columnName) {
    const column = state.columns.find((c) => c.column_name === columnName);
    return column ? column.inferred_type : "text";
}

function filterKind(columnName) {
    const type = typeOf(columnName);
    return NUMERIC.has(type) ? "number" : type;
}

function columnSelect(id, selected) {
    const select = el("select");
    select.id = id;
    for (const column of state.columns) select.append(option(column.column_name, column.column_name));
    if (selected !== undefined) select.value = selected;
    return select;
}

function field(labelText, control) {
    const wrapper = el("div", "field");
    const label = el("label", "", labelText);
    label.htmlFor = control.id;
    wrapper.append(label, control);
    return wrapper;
}

// ---------- Configuração de um gráfico <-> spec da API ----------

function configFromSpec(spec) {
    return {
        chart: spec.chart,
        dimension: spec.dimension ? spec.dimension.column : defaultDimension(),
        grain: (spec.dimension && spec.dimension.time_grain) || "month",
        metricColumn: spec.metrics[0].column,
        agg: spec.metrics[0].agg,
    };
}

function specFromConfig(config) {
    const spec = {
        chart: config.chart,
        metrics: [{ column: config.metricColumn, agg: config.agg }],
        filters: [],
        limit: 20,
    };
    if (config.chart !== "kpi") {
        spec.dimension = {
            column: config.dimension,
            time_grain: typeOf(config.dimension) === "datetime" ? config.grain : null,
        };
    }
    return spec;
}

function defaultDimension() {
    const preferred = state.columns.find((c) => c.inferred_type === "datetime")
        || state.columns.find((c) => c.inferred_type === "text")
        || state.columns[0];
    return preferred.column_name;
}

function autoTitle(config) {
    const measure = `${AGG_LABELS[config.agg]} de ${config.metricColumn}`;
    if (config.chart === "kpi") return measure;
    const grain = typeOf(config.dimension) === "datetime" ? ` (${GRAIN_LABELS[config.grain].toLowerCase()})` : "";
    return `${measure} por ${config.dimension}${grain}`;
}

// ---------- Execução ----------

function globalFiltersSpec() {
    return state.filters.map(filterToSpec).filter((f) => f !== null);
}

function scheduleRun(widget, delay = DEBOUNCE_MS) {
    clearTimeout(widget.timer);
    widget.timer = setTimeout(() => runWidget(widget), delay);
}

async function runWidget(widget) {
    const seq = ++widget.seq; // respostas antigas (de uma configuração anterior) são descartadas
    const spec = { ...specFromConfig(widget.config), filters: globalFiltersSpec() };
    widget.card.classList.add("is-loading");
    try {
        const result = await apiRequest(`/datasets/${DATASET_ID}/query`, {
            method: "POST",
            body: JSON.stringify(spec),
        });
        if (seq !== widget.seq) return;
        widget.last = { spec, result };
        renderResult(widget);
    } catch (err) {
        if (seq !== widget.seq) return;
        showWidgetError(widget, err.message);
    } finally {
        if (seq === widget.seq) widget.card.classList.remove("is-loading");
    }
}

function runAll() {
    for (const widget of state.widgets) scheduleRun(widget, 0);
}

// ---------- Desenho do corpo do card ----------

function setBodyMode(widget, mode) {
    if (widget.mode === mode && mode === "chart") return;
    if (widget.chart) {
        widget.chart.dispose();
        widget.chart = null;
    }
    widget.body.replaceChildren();
    widget.body.classList.toggle("widget__body--compact", mode === "kpi");
    widget.mode = mode;
}

function renderResult(widget) {
    const { spec, result } = widget.last;
    widget.title.textContent = autoTitle(widget.config);
    widget.error.hidden = true;

    const meta = [`${result.total_rows_matched.toLocaleString("pt-BR")} linha(s) consideradas`];
    if (result.truncated) meta.push(`mostrando só as ${spec.limit} primeiras categorias`);
    widget.meta.textContent = meta.join(" · ");

    if (spec.chart === "kpi") {
        setBodyMode(widget, "kpi");
        const value = el("div", "kpi-value", ChartAdapter.formatNumber(result.series[0].data[0]));
        widget.body.append(value, el("div", "kpi-label", result.series[0].name));
        return;
    }
    if (result.categories.length === 0) {
        setBodyMode(widget, "empty");
        widget.body.append(el("p", "widget__empty", "Sem dados para este recorte."));
        return;
    }
    if (widget.mode !== "chart") {
        setBodyMode(widget, "chart");
        const box = el("div", "chart-box");
        widget.body.append(box);
        widget.chart = ChartAdapter.mount(box);
    }
    widget.chart.render(spec, result);
}

function showWidgetError(widget, message) {
    setBodyMode(widget, "error");
    widget.error.textContent = message;
    widget.error.hidden = false;
    widget.meta.textContent = "";
}

// ---------- Cards ----------

function allowedAggs(columnName) {
    return NUMERIC.has(typeOf(columnName)) ? NUMERIC_AGGS : OTHER_AGGS;
}

function fillAggSelect(select, columnName, preferred) {
    const aggs = allowedAggs(columnName);
    select.replaceChildren(...aggs.map((agg) => option(agg, AGG_LABELS[agg])));
    select.value = aggs.includes(preferred) ? preferred : aggs[0];
}

function createWidget(spec) {
    const widget = {
        id: nextId++, config: configFromSpec(spec), seq: 0, timer: null, last: null, chart: null, mode: null,
    };
    const prefix = `w${widget.id}`;

    const card = el("article", "widget");
    const head = el("header", "widget__head");
    widget.title = el("h3", "widget__title", autoTitle(widget.config));
    const remove = el("button", "icon-button", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", "Remover gráfico");
    head.append(widget.title, remove);

    widget.body = el("div", "widget__body");
    widget.error = el("p", "alert alert--danger");
    widget.error.hidden = true;
    widget.meta = el("p", "widget__meta muted");

    const settings = el("details", "widget__settings");
    settings.append(el("summary", "", "Personalizar"));
    const controls = el("div", "widget__controls");

    const chartSelect = el("select");
    chartSelect.id = `${prefix}-chart`;
    for (const [value, label] of Object.entries(CHART_LABELS)) chartSelect.append(option(value, label));
    chartSelect.value = widget.config.chart;

    const dimSelect = columnSelect(`${prefix}-dim`, widget.config.dimension);
    const grainSelect = el("select");
    grainSelect.id = `${prefix}-grain`;
    for (const [value, label] of Object.entries(GRAIN_LABELS)) grainSelect.append(option(value, label));
    grainSelect.value = widget.config.grain;

    const metricSelect = columnSelect(`${prefix}-metric`, widget.config.metricColumn);
    const aggSelect = el("select");
    aggSelect.id = `${prefix}-agg`;
    fillAggSelect(aggSelect, widget.config.metricColumn, widget.config.agg);
    widget.config.agg = aggSelect.value;

    const dimField = field("Eixo X (agrupar por)", dimSelect);
    const grainField = field("Agrupar datas por", grainSelect);
    controls.append(field("Tipo de gráfico", chartSelect), dimField, grainField,
        field("Métrica (coluna)", metricSelect), field("Agregação", aggSelect));
    settings.append(controls);

    function refreshVisibility() {
        const isKpi = widget.config.chart === "kpi";
        dimField.hidden = isKpi;
        grainField.hidden = isKpi || typeOf(widget.config.dimension) !== "datetime";
    }

    function onControlChange(event) {
        if (event.target === metricSelect) fillAggSelect(aggSelect, metricSelect.value, aggSelect.value);
        widget.config = {
            chart: chartSelect.value,
            dimension: dimSelect.value,
            grain: grainSelect.value,
            metricColumn: metricSelect.value,
            agg: aggSelect.value,
        };
        refreshVisibility();
        widget.title.textContent = autoTitle(widget.config);
        scheduleRun(widget);
    }
    controls.addEventListener("change", onControlChange);

    remove.addEventListener("click", () => {
        clearTimeout(widget.timer);
        widget.seq += 1;
        if (widget.chart) widget.chart.dispose();
        card.remove();
        state.widgets = state.widgets.filter((w) => w !== widget);
    });

    card.append(head, widget.body, widget.error, widget.meta, settings);
    widget.card = card;
    refreshVisibility();
    widgetsBox.append(card);
    state.widgets.push(widget);
    scheduleRun(widget, 0);
    return widget;
}

function clearWidgets() {
    for (const widget of state.widgets) {
        clearTimeout(widget.timer);
        widget.seq += 1;
        if (widget.chart) widget.chart.dispose();
    }
    state.widgets = [];
    widgetsBox.replaceChildren();
}

// ---------- Filtros globais ----------

function filterToSpec(filter) {
    const kind = filterKind(filter.column);
    const raw = filter.raw.trim();
    if (raw === "") return null;
    let value;
    if (filter.op === "in") {
        const parts = raw.split(",").map((s) => s.trim()).filter(Boolean);
        value = kind === "number" ? parts.map(Number) : parts;
        if (!parts.length || (kind === "number" && value.some((n) => !Number.isFinite(n)))) return null;
    } else if (kind === "number") {
        value = Number(raw);
        if (!Number.isFinite(value)) return null;
    } else if (kind === "boolean") {
        value = raw === "true";
    } else {
        value = raw;
    }
    return { column: filter.column, op: filter.op, value };
}

function buildValueInput(filter) {
    const kind = filterKind(filter.column);
    let input;
    if (kind === "boolean") {
        input = el("select");
        input.append(option("true", "verdadeiro"), option("false", "falso"));
        filter.raw = input.value = "true";
    } else {
        input = el("input");
        input.type = kind === "number" && filter.op !== "in" ? "number" : kind === "datetime" ? "date" : "text";
        if (kind === "number") input.step = "any";
        input.value = filter.raw;
    }
    input.setAttribute("aria-label", "Valor do filtro");
    input.addEventListener("input", () => onFilterEdited(filter, input.value));
    input.addEventListener("change", () => onFilterEdited(filter, input.value));
    return input;
}

let filterTimer = null;
function onFilterEdited(filter, raw) {
    filter.raw = raw;
    clearTimeout(filterTimer);
    filterTimer = setTimeout(runAll, FILTER_DEBOUNCE_MS);
}

function addFilter() {
    if (state.columns.length === 0) return;
    const filter = { id: nextId++, column: state.columns[0].column_name, op: "eq", raw: "" };
    const row = el("div", "filter-row");
    const columnPicker = columnSelect(`f${filter.id}-col`, filter.column);
    columnPicker.setAttribute("aria-label", "Coluna do filtro");
    const opPicker = el("select");
    opPicker.setAttribute("aria-label", "Operador do filtro");
    let valueInput = buildValueInput(filter);
    const remove = el("button", "icon-button", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", "Remover filtro");

    function fillOps() {
        const ops = OPS_BY_TYPE[filterKind(filter.column)];
        opPicker.replaceChildren(...ops.map((op) => option(op, OP_LABELS[op])));
        filter.op = ops.includes(filter.op) ? filter.op : ops[0];
        opPicker.value = filter.op;
    }
    function rebuildValue() {
        const fresh = buildValueInput(filter);
        valueInput.replaceWith(fresh);
        valueInput = fresh;
    }

    columnPicker.addEventListener("change", () => {
        filter.column = columnPicker.value;
        filter.raw = "";
        fillOps();
        rebuildValue();
        onFilterEdited(filter, filter.raw);
    });
    opPicker.addEventListener("change", () => {
        filter.op = opPicker.value;
        rebuildValue();
        onFilterEdited(filter, filter.raw);
    });
    remove.addEventListener("click", () => {
        state.filters = state.filters.filter((f) => f !== filter);
        row.remove();
        onFilterEdited(filter, filter.raw);
    });

    fillOps();
    row.append(columnPicker, opPicker, valueInput, remove);
    filtersList.append(row);
    state.filters.push(filter);
}

// ---------- Inicialização ----------

async function loadSuggestions() {
    const widgets = await apiRequest(`/datasets/${DATASET_ID}/suggested-dashboard`);
    clearWidgets();
    for (const widget of widgets) createWidget(widget.spec);
    if (widgets.length === 0) {
        renderState(stateBox, {
            kind: "empty",
            title: "Nenhum gráfico sugerido",
            message: "As regras automáticas não encontraram colunas adequadas. Use \"Adicionar gráfico\" para montar o seu.",
        });
    } else {
        stateBox.hidden = true;
    }
}

function addDefaultWidget() {
    const dimension = defaultDimension();
    const measure = state.columns.find((c) => NUMERIC.has(c.inferred_type));
    createWidget({
        chart: "bar",
        dimension: { column: dimension, time_grain: "month" },
        metrics: [measure ? { column: measure.column_name, agg: "sum" } : { column: dimension, agg: "count" }],
    });
}

async function init() {
    try {
        const profile = await apiRequest(`/datasets/${DATASET_ID}/profile`);
        state.columns = profile.columns;
        try {
            const datasets = await apiRequest("/datasets");
            const current = datasets.find((d) => d.id === DATASET_ID);
            document.getElementById("dataset-name").textContent = current ? current.original_name : `Dataset ${DATASET_ID}`;
        } catch {
            document.getElementById("dataset-name").textContent = `Dataset ${DATASET_ID}`;
        }
        filtersCard.hidden = false;
        actionsBar.hidden = false;
        await loadSuggestions();
    } catch (err) {
        document.getElementById("dataset-name").textContent = `Dataset ${DATASET_ID}`;
        renderState(stateBox, {
            kind: "error",
            title: "Não foi possível montar o dashboard",
            message: err.status === 404
                ? "Dataset não encontrado, ou ainda não perfilado. Volte para Datasets e calcule o perfil primeiro."
                : err.message,
        });
    }
}

document.getElementById("add-filter").addEventListener("click", addFilter);
document.getElementById("add-widget").addEventListener("click", addDefaultWidget);
document.getElementById("reset-dashboard").addEventListener("click", async () => {
    const confirmed = await confirmAction({
        title: "Restaurar painel padrão?",
        message: "Os gráficos atuais (inclusive os que você personalizou) serão substituídos pelos sugeridos. Os filtros globais continuam.",
        confirmLabel: "Restaurar",
    });
    if (!confirmed) return;
    try {
        await loadSuggestions();
        showToast("Painel padrão restaurado.", "success");
    } catch (err) {
        showToast(err.message, "error");
    }
});

ChartAdapter.onThemeChange(() => {
    for (const widget of state.widgets) {
        if (widget.mode === "chart" && widget.last) widget.chart.render(widget.last.spec, widget.last.result);
    }
});

init();
