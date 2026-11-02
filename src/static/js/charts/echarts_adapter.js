// Adaptador entre o JSON da API ({categories, series}) e o Apache ECharts.
//
// Nomes de coluna e categorias vêm dos dados do usuário. Eles só entram no gráfico como dados
// do ECharts, e o tooltip usa `valueFormatter` (nunca `formatter` montando HTML com esses textos),
// então nada vindo do arquivo é interpretado como marcação.

const ChartAdapter = (() => {
    const numberFormat = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
    const compactFormat = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });

    function cssVar(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    function formatNumber(value) {
        return value === null || value === undefined ? "—" : numberFormat.format(value);
    }

    function palette() {
        return [cssVar("--accent"), cssVar("--success"), cssVar("--warning"), "#5a8fd9", cssVar("--danger"), "#9b7fd1"];
    }

    function buildOption(spec, result) {
        const muted = cssVar("--text-muted");
        const lines = cssVar("--border");
        const tooltip = {
            valueFormatter: formatNumber,
            backgroundColor: cssVar("--surface"),
            borderColor: lines,
            textStyle: { color: cssVar("--text") },
        };
        const base = {
            color: palette(),
            animationDuration: 300,
            textStyle: { color: muted, fontFamily: cssVar("--font") },
        };

        if (spec.chart === "pie") {
            return {
                ...base,
                tooltip: { ...tooltip, trigger: "item" },
                legend: { type: "scroll", bottom: 0, textStyle: { color: muted } },
                series: [{
                    type: "pie",
                    radius: ["42%", "68%"],
                    center: ["50%", "44%"],
                    itemStyle: { borderColor: cssVar("--surface"), borderWidth: 2 },
                    label: { color: muted },
                    data: result.categories.map((name, i) => ({ name, value: result.series[0].data[i] })),
                }],
            };
        }

        const multi = result.series.length > 1;
        return {
            ...base,
            tooltip: { ...tooltip, trigger: "axis" },
            legend: multi ? { top: 0, textStyle: { color: muted } } : undefined,
            grid: { left: 8, right: 16, top: multi ? 36 : 16, bottom: 8, containLabel: true },
            xAxis: {
                type: "category",
                data: result.categories,
                axisLine: { lineStyle: { color: lines } },
                axisLabel: { color: muted, hideOverlap: true },
            },
            yAxis: {
                type: "value",
                axisLabel: { color: muted, formatter: (value) => compactFormat.format(value) },
                splitLine: { lineStyle: { color: lines } },
            },
            series: result.series.map((s) => ({
                name: s.name,
                type: spec.chart,
                data: s.data,
                ...(spec.chart === "bar"
                    ? { itemStyle: { borderRadius: [3, 3, 0, 0] } }
                    : { showSymbol: result.categories.length <= 40 }),
            })),
        };
    }

    // Uma instância do ECharts por container. Quem monta é responsável por chamar dispose().
    function mount(container) {
        const chart = echarts.init(container);
        const observer = new ResizeObserver(() => chart.resize());
        observer.observe(container);
        return {
            render(spec, result) {
                chart.setOption(buildOption(spec, result), { notMerge: true });
            },
            dispose() {
                observer.disconnect();
                chart.dispose();
            },
        };
    }

    // As cores vêm das variáveis CSS do tema; ao alternar claro/escuro, quem usa o adaptador
    // precisa redesenhar.
    function onThemeChange(callback) {
        new MutationObserver(callback).observe(document.documentElement, {
            attributes: true,
            attributeFilter: ["data-theme"],
        });
    }

    return { mount, formatNumber, buildOption, onThemeChange };
})();
