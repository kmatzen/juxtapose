// One column spec per view, rendered as DOM nodes: data reaches the page only through
// textContent, so it cannot become markup. The string version needed esc() at ~20 call sites.

export type QuestionConfig = {
    name: string;
    type: string;
    section_label?: string;
    confidence?: boolean;
};

export type DemographicsField = {
    name: string;
    type: string;
    label: string;
};

export type SurveyConfig = {
    questions?: QuestionConfig[];
    demographics?: DemographicsField[];
    survey?: { pairs_per_user?: number };
};

export type Row = Record<string, unknown> & { email?: string; session_id?: string };

export type Stats = {
    participants?: number;
    avg_confidence?: number | null;
    avg_time?: number | null;
    preferences?: Record<string, Record<string, number>>;
};

export type ResultsPage = { rows?: Row[]; total?: number };

export type Column = {
    header: string;
    cell: (row: Row) => string;
    narrow?: boolean;
};

const PAGE_SIZE = 200;
const PLACEHOLDER = '-';

const text = (value: unknown): string =>
    value === null || value === undefined || value === '' ? PLACEHOLDER : String(value);

const num = (value: unknown): string => (value === null || value === undefined ? PLACEHOLDER : String(value));

export function formatTimeSpent(value: unknown): string {
    // Rows stored before the server coerced this column can hold text; blanking the table is worse.
    if (value === null || value === undefined || value === '') return PLACEHOLDER;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed.toFixed(1) : PLACEHOLDER;
}

function formatDate(value: unknown): string {
    if (!value) return PLACEHOLDER;
    const date = new Date(String(value));
    return Number.isNaN(date.getTime()) ? PLACEHOLDER : date.toLocaleDateString();
}

export function demographicsColumns(config: SurveyConfig): Column[] {
    const fields = (config.demographics || []).filter(field => field.type !== 'email');
    return [
        { header: 'Email', cell: row => text(row.email) },
        { header: 'Referral', cell: row => text(row.referral_code) },
        { header: 'Browser', narrow: true, cell: row => `${text(row.browser)} ${text(row.browser_version)}` },
        { header: 'OS', cell: row => text(row.os) },
        { header: 'Screen', narrow: true, cell: row => `${text(row.screen_width)}×${text(row.screen_height)}` },
        ...fields.map(field => ({ header: field.label, cell: (row: Row) => text(row[field.name]) })),
        { header: 'Responses', cell: row => `${num(row.responseCount)}/${num(row.pairsPerUser)}` },
    ];
}

export function responseColumns(questions: QuestionConfig[]): Column[] {
    const columns: Column[] = [
        { header: 'Date', narrow: true, cell: row => formatDate(row.response_created) },
        { header: 'Email', cell: row => text(row.email) },
        { header: 'Pair#', cell: row => text(row.image_pair_id) },
        { header: 'Method A', narrow: true, cell: row => text(row.method_a) },
        { header: 'Method B', narrow: true, cell: row => text(row.method_b) },
    ];

    for (const question of questions.filter(q => q.type === 'ab_preference')) {
        const label = question.section_label || question.name;
        columns.push(
            { header: `Choice (${label})`, cell: row => text(row[`${question.name}_choice`]) },
            { header: `Preferred (${label})`, cell: row => text(row[`${question.name}_preferred_method`]) },
        );
        if (question.confidence) {
            columns.push({ header: `Conf (${label})`, cell: row => num(row[`${question.name}_confidence`]) });
        }
    }

    columns.push({ header: 'Time (s)', cell: row => formatTimeSpent(row.time_spent) });
    return columns;
}

export function preferenceSummary(stats: Stats | null, name: string): string {
    const prefs = (stats?.preferences || {})[name] || {};
    return Object.keys(prefs).map(method => `${method}: ${prefs[method]}`).join(', ') || 'No data';
}

export function renderHeader(thead: HTMLElement, columns: Column[]): void {
    const tr = document.createElement('tr');
    for (const column of columns) {
        const th = document.createElement('th');
        th.textContent = column.header;
        tr.appendChild(th);
    }
    thead.replaceChildren(tr);
}

export function renderRows(tbody: HTMLElement, rows: Row[], columns: Column[]): void {
    const fragment = document.createDocumentFragment();
    for (const row of rows) {
        const tr = document.createElement('tr');
        for (const column of columns) {
            const td = document.createElement('td');
            td.textContent = column.cell(row);
            if (column.narrow) td.classList.add('cell-narrow');
            tr.appendChild(td);
        }
        fragment.appendChild(tr);
    }
    tbody.replaceChildren(fragment);
}

function renderMessage(tbody: HTMLElement, message: string, columns: Column[]): void {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = Math.max(columns.length, 1);
    td.textContent = message;
    tr.appendChild(td);
    tbody.replaceChildren(tr);
}

function by<T>(id: string): T | null {
    return document.getElementById(id) as T | null;
}

const state = {
    view: 'demographics' as 'demographics' | 'responses',
    rows: [] as Row[],
    total: 0,
    config: null as SurveyConfig | null,
    stats: null as Stats | null,
};

async function getJson<T>(url: string): Promise<T> {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${url} responded ${response.status}`);
    return response.json() as Promise<T>;
}

function columnsForView(): Column[] {
    const config = state.config || {};
    return state.view === 'demographics'
        ? demographicsColumns(config)
        : responseColumns(config.questions || []);
}

function renderStats(): void {
    const stats = state.stats;
    if (!stats || !state.config) return;

    const total = by<HTMLElement>('total-responses');
    const confidence = by<HTMLElement>('avg-confidence');
    const avgTime = by<HTMLElement>('avg-time');
    if (total) total.textContent = num(stats.participants);
    if (confidence) confidence.textContent = num(stats.avg_confidence);
    if (avgTime) avgTime.textContent = num(stats.avg_time);

    const cards: Element[] = [];
    for (const question of (state.config.questions || []).filter(q => q.type === 'ab_preference')) {
        const card = document.createElement('div');
        card.className = 'stat-card pref-card';
        const numbers = document.createElement('div');
        numbers.className = 'stat-number pref-summary';
        numbers.textContent = preferenceSummary(stats, question.name);
        const label = document.createElement('div');
        label.className = 'stat-label';
        label.textContent = `Preferences: ${question.section_label || question.name}`;
        card.append(numbers, label);
        cards.push(card);
    }
    by<HTMLElement>('method-pref-cards')?.replaceChildren(...cards);
}

function renderTable(): void {
    const thead = by<HTMLElement>('table-header');
    const tbody = by<HTMLElement>('results-body');
    if (!thead || !tbody) return;

    const columns = columnsForView();

    if (state.rows.length === 0) {
        thead.replaceChildren();
        renderMessage(tbody, 'No responses yet', columns);
    } else {
        renderHeader(thead, columns);
        renderRows(tbody, viewRows(), columns);
    }

    const loadMoreButton = by<HTMLElement>('load-more');
    if (loadMoreButton) {
        loadMoreButton.style.display = state.rows.length < state.total ? 'inline-block' : 'none';
    }
    const rowCount = by<HTMLElement>('row-count');
    if (rowCount) rowCount.textContent = `Showing ${state.rows.length} of ${state.total} responses`;
}

export function groupParticipants(rows: Row[], pairsPerUser: number): Row[] {
    // The demographics view is one row per participant: responses are counted, not listed.
    const participants = new Map<string, Row>();
    for (const row of rows) {
        const key = row.email || row.session_id || '';
        const existing = participants.get(key);
        if (existing) {
            existing.responseCount = Number(existing.responseCount) + 1;
        } else {
            participants.set(key, { ...row, responseCount: 1, pairsPerUser });
        }
    }
    return [...participants.values()];
}

function viewRows(): Row[] {
    if (state.view !== 'demographics') return state.rows;
    return groupParticipants(state.rows, state.config?.survey?.pairs_per_user ?? 30);
}

async function loadStats(): Promise<void> {
    try {
        state.stats = await getJson<Stats>('/api/admin/stats');
        renderStats();
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function loadRows(offset = 0): Promise<void> {
    const tbody = by<HTMLElement>('results-body');
    try {
        const page = await getJson<ResultsPage>(`/api/admin/results?limit=${PAGE_SIZE}&offset=${offset}`);
        state.rows = offset > 0 ? state.rows.concat(page.rows || []) : page.rows || [];
        state.total = page.total ?? state.rows.length;
    } catch (error) {
        console.error('Error loading results:', error);
        state.rows = [];
        state.total = 0;
        if (tbody) renderMessage(tbody, 'Error loading results', columnsForView());
        return;
    }
    renderTable();
}

async function refresh(): Promise<void> {
    await Promise.all([loadStats(), loadRows(0)]);
}

function toggleView(): void {
    state.view = state.view === 'demographics' ? 'responses' : 'demographics';
    const mode = by<HTMLElement>('view-mode');
    if (mode) mode.textContent = state.view === 'demographics' ? 'Demographics View' : 'Responses View';
    renderTable();
}

async function deleteByEmail(): Promise<void> {
    const emailInput = by<HTMLInputElement>('delete-email');
    const message = by<HTMLElement>('delete-message');
    const email = (emailInput?.value || '').trim();
    if (!emailInput || !message) return;

    const say = (color: string, body: string) => {
        message.style.display = 'block';
        message.style.color = color;
        message.textContent = body;
    };

    if (!email) {
        say('#e74c3c', 'Please enter an email address.');
        return;
    }
    const warning = `Permanently delete ALL records for "${email}"?\n\nThis deletes the participant, their demographics and every response. This cannot be undone.`;
    if (!window.confirm(warning)) return;

    say('#666', 'Deleting...');
    try {
        const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        const response = await fetch('/api/admin/delete_by_email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
            body: JSON.stringify({ email }),
        });
        const result = await response.json();
        if (!response.ok) {
            say('#e74c3c', `Error: ${result.error}`);
            return;
        }
        say('#52c41a', `Deleted ${result.participants_deleted} participant(s), `
            + `${result.demographics_deleted} demographics record(s) and `
            + `${result.responses_deleted} response(s) for "${result.email}".`);
        emailInput.value = '';
        await refresh();
    } catch (error) {
        say('#e74c3c', `Error: ${(error as Error).message}`);
    }
}

export async function init(): Promise<void> {
    state.config = await getJson<SurveyConfig>('/api/config');
    await refresh();
    setInterval(refresh, 30000);
}

export function wire(page: Document): void {
    page.getElementById('toggle-view')?.addEventListener('click', toggleView);
    page.getElementById('load-more')?.addEventListener('click', () => { void loadRows(state.rows.length); });
    page.getElementById('export-csv')?.addEventListener('click', () => { window.location.href = '/api/admin/export'; });
    page.getElementById('logout')?.addEventListener('click', () => { window.location.href = '/admin/logout'; });
    page.getElementById('delete-records')?.addEventListener('click', () => { void deleteByEmail(); });
}

// The page marker keeps unit tests (which import these functions) from booting the dashboard.
if (typeof document !== 'undefined' && document.querySelector('[data-admin-app]')) {
    wire(document);
    void init();
}
