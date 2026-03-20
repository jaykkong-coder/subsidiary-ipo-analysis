let DATA = null;
let WD_DATA = null;
let PRICE_CACHE = {};

const COLORS = {
    primary: '#0c2461',
    blue: '#1e3799',
    red: '#d63031',
    green: '#00b894',
    gray: '#636e72',
    lightBlue: '#74b9ff',
    orange: '#e17055',
};

// === Helpers ===
const fmtRet = (v) => {
    if (v === null || v === undefined) return '-';
    const pct = (v * 100).toFixed(1);
    const cls = v >= 0 ? 'return-positive' : 'return-negative';
    return `<span class="${cls}">${v >= 0 ? '+' : ''}${pct}%</span>`;
};
const fmtRetTd = (v) => {
    if (v === null || v === undefined) return '<td>-</td>';
    const pct = (v * 100).toFixed(1);
    const cls = v >= 0 ? 'ret-pos' : 'ret-neg';
    return `<td class="${cls}">${v >= 0 ? '+' : ''}${pct}%</td>`;
};
const fmtMcap = (v) => v ? (v / 10000).toFixed(1) + '조원' : '-';
const fmtRatio = (v) => v !== null && v !== undefined ? (v * 100).toFixed(1) + '%' : '-';
const fmtPct = (v) => (v === null || v === undefined) ? '-' : (v * 100).toFixed(1);

// === Data Loading ===
async function loadData() {
    const [resp, wdResp] = await Promise.all([
        fetch('data/analysis_result.json'),
        fetch('data/withdrawn_result.json').catch(() => null),
    ]);
    DATA = await resp.json();
    if (wdResp && wdResp.ok) WD_DATA = await wdResp.json();

    renderAll();
    if (WD_DATA) renderWithdrawnAll();
    initTabs();
}

async function loadPriceCSV(ticker) {
    if (PRICE_CACHE[ticker]) return PRICE_CACHE[ticker];
    const resp = await fetch(`data/${ticker}.csv`);
    const text = await resp.text();
    const result = Papa.parse(text, { header: true, skipEmptyLines: true });
    PRICE_CACHE[ticker] = result.data;
    return result.data;
}

// === Tab Navigation ===
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
        });
    });
}

// =============================================
// COMPLETED TAB
// =============================================
function renderAll() {
    renderSummaryCards();
    renderCaseSelector();
    renderComparisonCharts();
    renderTable();
    document.getElementById('gen-date').textContent = DATA.generated_at.split('T')[0];
}

function renderSummaryCards() {
    const container = document.getElementById('summary-cards');
    const splitCount = DATA.cases.filter(c => c.type === '물적분할').length;
    const ipoCount = DATA.cases.filter(c => c.type === '기존자회사IPO').length;

    const annD0 = DATA.cases.map(c => c.metrics.returns.announcement_D0).filter(v => v != null);
    const avgAnnD0 = annD0.length > 0 ? (annD0.reduce((a, b) => a + b, 0) / annD0.length * 100).toFixed(1) : 'N/A';

    const ipo30 = DATA.cases.map(c => c.metrics.returns.ipo_30d).filter(v => v != null);
    const avgIpo30 = ipo30.length > 0 ? (ipo30.reduce((a, b) => a + b, 0) / ipo30.length * 100).toFixed(1) : 'N/A';

    container.innerHTML = `
        <div class="card">
            <div class="label">전체 케이스</div>
            <div class="value">${DATA.total_cases}</div>
            <div class="sub">물적분할 ${splitCount} / 기존자회사 ${ipoCount}</div>
        </div>
        <div class="card">
            <div class="label">발표 당일 평균</div>
            <div class="value" style="color:${parseFloat(avgAnnD0) >= 0 ? COLORS.red : COLORS.blue}">${avgAnnD0}%</div>
            <div class="sub">모회사 주가 변동률</div>
        </div>
        <div class="card">
            <div class="label">상장 후 30일 평균</div>
            <div class="value" style="color:${parseFloat(avgIpo30) >= 0 ? COLORS.red : COLORS.blue}">${avgIpo30}%</div>
            <div class="sub">모회사 주가 변동률</div>
        </div>
        <div class="card">
            <div class="label">분석 기간</div>
            <div class="value" style="font-size:1.3rem">2017-2026</div>
            <div class="sub">최근 약 10년</div>
        </div>
    `;
}

function renderCaseSelector() {
    const sel = document.getElementById('case-selector');
    DATA.cases.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = `${c.parent.name} → ${c.subsidiary.name} (${c.type})`;
        sel.appendChild(opt);
    });
    sel.addEventListener('change', () => {
        if (sel.value) renderCaseDetail(sel.value);
    });
    if (DATA.cases.length > 0) {
        sel.value = DATA.cases[0].id;
        renderCaseDetail(DATA.cases[0].id);
    }
}

async function renderCaseDetail(caseId) {
    const c = DATA.cases.find(x => x.id === caseId);
    if (!c) return;

    const infoBox = document.getElementById('case-info');
    infoBox.style.display = 'grid';
    const ret = c.metrics.returns;

    infoBox.innerHTML = `
        <div class="info-item"><div class="label">모회사</div><div class="value">${c.parent.name}</div></div>
        <div class="info-item"><div class="label">자회사</div><div class="value">${c.subsidiary.name}</div></div>
        <div class="info-item"><div class="label">유형</div><div class="value">${c.type}</div></div>
        <div class="info-item"><div class="label">발표일</div><div class="value">${c.events.split_announcement}</div></div>
        <div class="info-item"><div class="label">상장일</div><div class="value">${c.events.ipo_date}</div></div>
        <div class="info-item"><div class="label">매출비중</div><div class="value">${fmtRatio(c.metrics.revenue_ratio)}</div></div>
        <div class="info-item"><div class="label">이익비중</div><div class="value">${fmtRatio(c.metrics.op_income_ratio)}</div></div>
        <div class="info-item"><div class="label">모회사 시총</div><div class="value">${fmtMcap(c.metrics.parent_market_cap)}</div></div>
        <div class="info-item"><div class="label">자회사 시총</div><div class="value">${fmtMcap(c.metrics.subsidiary_market_cap)}</div></div>
        <div class="info-item"><div class="label">자/모 시총비율</div><div class="value">${fmtRatio(c.metrics.mcap_ratio)}</div></div>
        <div class="info-item"><div class="label">발표 당일</div><div class="value">${fmtRet(ret.announcement_D0)}</div></div>
        <div class="info-item"><div class="label">발표후 30일</div><div class="value">${fmtRet(ret.announcement_30d)}</div></div>
        <div class="info-item"><div class="label">상장 당일</div><div class="value">${fmtRet(ret.ipo_D0)}</div></div>
        <div class="info-item"><div class="label">상장후 30일</div><div class="value">${fmtRet(ret.ipo_30d)}</div></div>
    `;

    await renderPriceChart(c.parent.ticker, c.events.split_announcement, 'case-chart', c.parent.name, [
        { date: c.events.split_announcement, label: '발표일', color: COLORS.blue, ret: ret.announcement_D0 },
        { date: c.events.ipo_date, label: '상장일', color: COLORS.red, ret: ret.ipo_D0 },
    ]);
}

async function renderPriceChart(ticker, annDateStr, chartEl, title, markers) {
    const priceData = await loadPriceCSV(ticker);
    if (!priceData || priceData.length === 0) return;

    const firstRow = priceData[0];
    const dateKey = Object.keys(firstRow)[0];
    const closeKey = Object.keys(firstRow).find(k => k.includes('종가')) || Object.keys(firstRow)[1];

    const dates = priceData.map(r => r[dateKey]);
    const closes = priceData.map(r => parseFloat(r[closeKey]));

    const trace = {
        x: dates, y: closes,
        type: 'scatter', mode: 'lines',
        name: title,
        line: { color: COLORS.primary, width: 1.5 },
    };

    const shapes = [];
    const annotations = [];

    markers.forEach(m => {
        if (!m.date) return;
        shapes.push({
            type: 'line',
            x0: m.date, x1: m.date, y0: 0, y1: 1, yref: 'paper',
            line: { color: m.color, width: 2, dash: 'dash' },
        });
        annotations.push({
            x: m.date, y: 1.05, yref: 'paper',
            text: `${m.label} (${fmtRet(m.ret).replace(/<[^>]*>/g, '')})`,
            showarrow: false,
            font: { color: m.color, size: 11 },
        });
    });

    // x축 범위: min(발표일-3개월, 오늘-5년) ~ 오늘
    const today = new Date();
    const annDate = new Date(annDateStr);
    const threeMonthsBefore = new Date(annDate);
    threeMonthsBefore.setMonth(threeMonthsBefore.getMonth() - 3);
    const fiveYearsAgo = new Date(today);
    fiveYearsAgo.setFullYear(fiveYearsAgo.getFullYear() - 5);
    const chartStart = threeMonthsBefore < fiveYearsAgo ? threeMonthsBefore : fiveYearsAgo;
    const xStart = chartStart.toISOString().split('T')[0];
    const xEnd = today.toISOString().split('T')[0];

    const layout = {
        title: { text: `${title} 주가`, font: { size: 15 } },
        xaxis: { title: '', type: 'date', range: [xStart, xEnd] },
        yaxis: { title: '주가 (원)', tickformat: ',.0f' },
        shapes, annotations,
        margin: { t: 50, b: 40, l: 70, r: 20 },
        height: 420,
        hovermode: 'x unified',
    };

    Plotly.newPlot(chartEl, [trace], layout, { responsive: true });
}

function renderComparisonCharts() {
    const cases = DATA.cases;

    // 1. 매출비중 vs 상장후30일 산점도 (카카오뱅크 제외 - 은행업 매출 기준 상이)
    const revCases = cases.filter(c => c.metrics.revenue_ratio !== null && c.metrics.returns.ipo_30d !== null && c.id !== 'kakao_kakaobank');
    Plotly.newPlot('scatter-revenue', [{
        x: revCases.map(c => c.metrics.revenue_ratio * 100),
        y: revCases.map(c => c.metrics.returns.ipo_30d * 100),
        text: revCases.map(c => `${c.parent.name}→${c.subsidiary.name}`),
        mode: 'markers+text', textposition: 'top center', textfont: { size: 9 },
        marker: { size: 12, color: revCases.map(c => c.type === '물적분할' ? COLORS.blue : COLORS.orange) },
        type: 'scatter',
    }], {
        title: { text: '매출비중 vs 상장후 30일 수익률', font: { size: 13 } },
        xaxis: { title: '자회사 매출비중 (%)', zeroline: true },
        yaxis: { title: '모회사 수익률 (%)', zeroline: true, zerolinecolor: '#ccc' },
        margin: { t: 40, b: 50, l: 50, r: 20 }, height: 350,
        shapes: [{ type: 'line', x0: 0, x1: 100, y0: 0, y1: 0, line: { color: '#ccc', dash: 'dot' } }],
    }, { responsive: true });

    // 2. 자/모 시총비율 vs 상장후30일
    const mcapCases = cases.filter(c => c.metrics.mcap_ratio !== null && c.metrics.returns.ipo_30d !== null);
    Plotly.newPlot('scatter-opincome', [{
        x: mcapCases.map(c => c.metrics.mcap_ratio * 100),
        y: mcapCases.map(c => c.metrics.returns.ipo_30d * 100),
        text: mcapCases.map(c => `${c.parent.name}→${c.subsidiary.name}`),
        mode: 'markers+text', textposition: 'top center', textfont: { size: 9 },
        marker: { size: 12, color: mcapCases.map(c => c.type === '물적분할' ? COLORS.blue : COLORS.orange) },
        type: 'scatter',
    }], {
        title: { text: '자/모 시총비율 vs 상장후 30일 수익률', font: { size: 13 } },
        xaxis: { title: '자회사/모회사 시총비율 (%)', zeroline: true },
        yaxis: { title: '모회사 수익률 (%)', zeroline: true, zerolinecolor: '#ccc' },
        margin: { t: 40, b: 50, l: 50, r: 20 }, height: 350,
        shapes: [{ type: 'line', x0: 0, x1: 200, y0: 0, y1: 0, line: { color: '#ccc', dash: 'dot' } }],
    }, { responsive: true });

    // 3. 상장유형별 평균 수익률
    const types = ['물적분할', '기존자회사IPO'];
    const periods = ['announcement_D0', 'announcement_30d', 'ipo_D0', 'ipo_30d'];
    const periodLabels = ['발표당일', '발표+30일', '상장당일', '상장+30일'];
    const barTraces = types.map((typ, i) => {
        const group = cases.filter(c => c.type === typ);
        const avgs = periods.map(p => {
            const vals = group.map(c => c.metrics.returns[p]).filter(v => v != null);
            return vals.length > 0 ? (vals.reduce((a, b) => a + b, 0) / vals.length * 100) : 0;
        });
        return { x: periodLabels, y: avgs, name: typ, type: 'bar', marker: { color: i === 0 ? COLORS.blue : COLORS.orange } };
    });
    Plotly.newPlot('bar-type', barTraces, {
        title: { text: '상장유형별 평균 수익률 (%)', font: { size: 13 } },
        barmode: 'group', yaxis: { title: '수익률 (%)', zeroline: true, zerolinecolor: '#ccc' },
        margin: { t: 40, b: 50, l: 50, r: 20 }, height: 350, legend: { x: 0.01, y: 0.99 },
        shapes: [{ type: 'line', x0: -0.5, x1: 3.5, y0: 0, y1: 0, line: { color: '#ccc', dash: 'dot' } }],
    }, { responsive: true });

    // 4. 시총비율 그룹별 박스플롯
    const mcapGroups = ['고비율(50%+)', '중비율(20-50%)', '저비율(<20%)'];
    const mcapTraces = mcapGroups.map((g, i) => {
        const group = cases.filter(c => c.metrics.mcap_ratio_group === g);
        const vals = group.map(c => c.metrics.returns.ipo_30d).filter(v => v != null);
        return { y: vals.map(v => v * 100), name: g, type: 'box', marker: { color: [COLORS.red, COLORS.orange, COLORS.green][i] } };
    });
    Plotly.newPlot('bar-mcap', mcapTraces, {
        title: { text: '자/모 시총비율별 상장후 30일 수익률', font: { size: 13 } },
        yaxis: { title: '모회사 수익률 (%)', zeroline: true, zerolinecolor: '#ccc' },
        margin: { t: 40, b: 40, l: 50, r: 20 }, height: 350, showlegend: true,
        shapes: [{ type: 'line', x0: -0.5, x1: 2.5, y0: 0, y1: 0, line: { color: '#ccc', dash: 'dot' } }],
    }, { responsive: true });
}

function renderTable() {
    const tbody = document.querySelector('#case-table tbody');
    tbody.innerHTML = DATA.cases.map(c => {
        const finYear = c.metrics.financial_year ? `${c.metrics.financial_year}년` : '-';
        const mcapDate = c.metrics.mcap_base_date || '-';
        return `
        <tr>
            <td>${c.parent.name}</td>
            <td>${c.subsidiary.name}</td>
            <td>${c.type}</td>
            <td>${fmtPct(c.metrics.revenue_ratio)}%<br><span class="basis-date">${finYear}</span></td>
            <td>${fmtPct(c.metrics.mcap_ratio)}%<br><span class="basis-date">${mcapDate}</span></td>
            ${fmtRetTd(c.metrics.returns.announcement_D0)}
            ${fmtRetTd(c.metrics.returns.announcement_30d)}
            ${fmtRetTd(c.metrics.returns.ipo_D0)}
            ${fmtRetTd(c.metrics.returns.ipo_30d)}
        </tr>
        `;
    }).join('');
}

// =============================================
// WITHDRAWN TAB
// =============================================
function renderWithdrawnAll() {
    renderWdSummaryCards();
    renderWdCaseSelector();
    renderWdComparisonCharts();
    renderWdTable();
}

function renderWdSummaryCards() {
    const container = document.getElementById('wd-summary-cards');
    const cases = WD_DATA.cases;
    const splitCount = cases.filter(c => c.type === '물적분할').length;
    const ipoCount = cases.filter(c => c.type !== '물적분할').length;

    const annD0 = cases.map(c => c.metrics.returns.announcement_D0).filter(v => v != null);
    const avgAnnD0 = annD0.length > 0 ? (annD0.reduce((a, b) => a + b, 0) / annD0.length * 100).toFixed(1) : 'N/A';

    const wdD0 = cases.map(c => c.metrics.returns.withdrawal_D0).filter(v => v != null);
    const avgWdD0 = wdD0.length > 0 ? (wdD0.reduce((a, b) => a + b, 0) / wdD0.length * 100).toFixed(1) : 'N/A';

    container.innerHTML = `
        <div class="card">
            <div class="label">불발 케이스</div>
            <div class="value">${cases.length}</div>
            <div class="sub">물적분할 ${splitCount} / 기타 ${ipoCount}</div>
        </div>
        <div class="card">
            <div class="label">추진 발표 당일 평균</div>
            <div class="value" style="color:${parseFloat(avgAnnD0) >= 0 ? COLORS.red : COLORS.blue}">${avgAnnD0}%</div>
            <div class="sub">모회사 주가 변동률</div>
        </div>
        <div class="card">
            <div class="label">철회 발표 당일 평균</div>
            <div class="value" style="color:${parseFloat(avgWdD0) >= 0 ? COLORS.red : COLORS.blue}">${avgWdD0}%</div>
            <div class="sub">모회사 주가 변동률</div>
        </div>
    `;
}

function renderWdCaseSelector() {
    const sel = document.getElementById('wd-case-selector');
    WD_DATA.cases.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = `${c.parent.name} → ${c.subsidiary.name} (${c.type})`;
        sel.appendChild(opt);
    });
    sel.addEventListener('change', () => {
        if (sel.value) renderWdCaseDetail(sel.value);
    });
    if (WD_DATA.cases.length > 0) {
        sel.value = WD_DATA.cases[0].id;
        renderWdCaseDetail(WD_DATA.cases[0].id);
    }
}

async function renderWdCaseDetail(caseId) {
    const c = WD_DATA.cases.find(x => x.id === caseId);
    if (!c) return;

    const infoBox = document.getElementById('wd-case-info');
    infoBox.style.display = 'grid';
    const ret = c.metrics.returns;

    infoBox.innerHTML = `
        <div class="info-item"><div class="label">모회사</div><div class="value">${c.parent.name}</div></div>
        <div class="info-item"><div class="label">자회사</div><div class="value">${c.subsidiary.name}</div></div>
        <div class="info-item"><div class="label">유형</div><div class="value">${c.type}</div></div>
        <div class="info-item"><div class="label">추진발표일</div><div class="value">${c.events.announcement}</div></div>
        <div class="info-item"><div class="label">철회일</div><div class="value">${c.events.withdrawal}</div></div>
        <div class="info-item"><div class="label">철회사유</div><div class="value">${c.withdrawal_reason}</div></div>
        <div class="info-item"><div class="label">발표 당일</div><div class="value">${fmtRet(ret.announcement_D0)}</div></div>
        <div class="info-item"><div class="label">발표후 30일</div><div class="value">${fmtRet(ret.announcement_30d)}</div></div>
        <div class="info-item"><div class="label">철회 당일</div><div class="value">${fmtRet(ret.withdrawal_D0)}</div></div>
        <div class="info-item"><div class="label">철회후 30일</div><div class="value">${fmtRet(ret.withdrawal_30d)}</div></div>
    `;

    await renderPriceChart(c.parent.ticker, c.events.announcement, 'wd-case-chart', c.parent.name, [
        { date: c.events.announcement, label: '추진발표', color: COLORS.orange, ret: ret.announcement_D0 },
        { date: c.events.withdrawal, label: '철회', color: COLORS.green, ret: ret.withdrawal_D0 },
    ]);
}

function renderWdComparisonCharts() {
    const cases = WD_DATA.cases;

    // 발표 vs 철회 당일 수익률 비교
    const barData = [
        {
            x: cases.map(c => c.parent.name),
            y: cases.map(c => (c.metrics.returns.announcement_D0 || 0) * 100),
            name: '추진발표 당일',
            type: 'bar',
            marker: { color: COLORS.orange },
        },
        {
            x: cases.map(c => c.parent.name),
            y: cases.map(c => (c.metrics.returns.withdrawal_D0 || 0) * 100),
            name: '철회 당일',
            type: 'bar',
            marker: { color: COLORS.green },
        },
    ];
    Plotly.newPlot('wd-bar-type', barData, {
        title: { text: '추진발표 vs 철회 당일 수익률 (%)', font: { size: 13 } },
        barmode: 'group',
        yaxis: { title: '수익률 (%)', zeroline: true, zerolinecolor: '#ccc' },
        xaxis: { tickangle: -30 },
        margin: { t: 40, b: 80, l: 50, r: 20 }, height: 350,
        legend: { x: 0.01, y: 0.99 },
        shapes: [{ type: 'line', x0: -0.5, x1: cases.length - 0.5, y0: 0, y1: 0, line: { color: '#ccc', dash: 'dot' } }],
    }, { responsive: true });

    // 철회 사유별 그룹 분석
    const reasons = {};
    cases.forEach(c => {
        const reason = c.withdrawal_reason.includes('소액주주') ? '주주반발' :
                       c.withdrawal_reason.includes('수요예측') ? '수요예측부진' :
                       c.withdrawal_reason.includes('중복상장') ? '중복상장규제' : '기타';
        if (!reasons[reason]) reasons[reason] = [];
        reasons[reason].push(c);
    });

    const reasonNames = Object.keys(reasons);
    const reasonTraces = [{
        x: reasonNames,
        y: reasonNames.map(r => {
            const rets = reasons[r].map(c => c.metrics.returns.announcement_30d).filter(v => v != null);
            return rets.length > 0 ? (rets.reduce((a, b) => a + b, 0) / rets.length * 100) : 0;
        }),
        name: '발표후 30일',
        type: 'bar',
        marker: { color: COLORS.orange },
    }, {
        x: reasonNames,
        y: reasonNames.map(r => {
            const rets = reasons[r].map(c => c.metrics.returns.withdrawal_30d).filter(v => v != null);
            return rets.length > 0 ? (rets.reduce((a, b) => a + b, 0) / rets.length * 100) : 0;
        }),
        name: '철회후 30일',
        type: 'bar',
        marker: { color: COLORS.green },
    }];
    Plotly.newPlot('wd-bar-reason', reasonTraces, {
        title: { text: '철회 사유별 평균 수익률 (%)', font: { size: 13 } },
        barmode: 'group',
        yaxis: { title: '수익률 (%)', zeroline: true, zerolinecolor: '#ccc' },
        margin: { t: 40, b: 50, l: 50, r: 20 }, height: 350,
        legend: { x: 0.01, y: 0.99 },
        shapes: [{ type: 'line', x0: -0.5, x1: reasonNames.length - 0.5, y0: 0, y1: 0, line: { color: '#ccc', dash: 'dot' } }],
    }, { responsive: true });
}

function renderWdTable() {
    const tbody = document.querySelector('#wd-case-table tbody');
    tbody.innerHTML = WD_DATA.cases.map(c => `
        <tr>
            <td>${c.parent.name}</td>
            <td>${c.subsidiary.name}</td>
            <td>${c.type}</td>
            <td>${c.events.announcement}</td>
            <td>${c.events.withdrawal}</td>
            <td style="font-size:0.8rem">${c.withdrawal_reason}</td>
            ${fmtRetTd(c.metrics.returns.announcement_D0)}
            ${fmtRetTd(c.metrics.returns.announcement_30d)}
            ${fmtRetTd(c.metrics.returns.withdrawal_D0)}
            ${fmtRetTd(c.metrics.returns.withdrawal_30d)}
        </tr>
    `).join('');
}

// Init
window.onerror = (msg, src, line, col, err) => {
    document.body.insertAdjacentHTML('afterbegin',
        `<pre style="color:red;background:#fff;padding:1rem;border:2px solid red;margin:1rem;">ERROR: ${msg}\nat ${src}:${line}:${col}\n${err?.stack || ''}</pre>`);
};
loadData().catch(err => {
    document.body.insertAdjacentHTML('afterbegin',
        `<pre style="color:red;background:#fff;padding:1rem;border:2px solid red;margin:1rem;">LOAD ERROR: ${err.message}\n${err.stack}</pre>`);
});
