import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  demographicsColumns,
  formatTimeSpent,
  preferenceSummary,
  renderHeader,
  renderRows,
  responseColumns,
  type QuestionConfig,
  type Row,
} from '../src/admin';

const QUESTIONS: QuestionConfig[] = [
  { name: 'image_quality', type: 'ab_preference', confidence: true, section_label: 'Image Quality' },
  { name: 'mask_adherence', type: 'ab_preference', confidence: true, section_label: 'Mask Adherence' },
  { name: 'comment', type: 'free_text' },
];

const el = (tag: string) => document.createElement(tag);

beforeEach(() => {
  document.body.innerHTML = '<table><thead id="table-header"></thead><tbody id="results-body"></tbody></table>';
});

describe('column specs', () => {
  it('gives one column per recorded value of every question type', () => {
    const headers = responseColumns(QUESTIONS).map(c => c.header);
    expect(headers).toEqual([
      'Date', 'Email', 'Pair#', 'Method A', 'Method B',
      'Choice (Image Quality)', 'Preferred (Image Quality)', 'Conf (Image Quality)',
      'Choice (Mask Adherence)', 'Preferred (Mask Adherence)', 'Conf (Mask Adherence)',
      'Answer (comment)',
      'Time (s)', 'Timing',
    ]);
  });

  it('shows the answer of a non-A/B question and the timing flag', () => {
    const columns = responseColumns(QUESTIONS);
    const cell = (header: string) =>
      columns.find(c => c.header === header)!.cell({ comment_text: 'lighting is flat', timing_flag: 1 });

    expect(cell('Answer (comment)')).toBe('lighting is flat');
    expect(cell('Timing')).toBe('not a judgement');
  });

  it('keeps header and cells in lockstep because both come from the spec', () => {
    const columns = responseColumns(QUESTIONS);
    const tbody = document.getElementById('results-body')!;
    renderHeader(document.getElementById('table-header')!, columns);
    renderRows(tbody, [{ email: 'a@b.c' }], columns);
    expect(document.querySelectorAll('#table-header th')).toHaveLength(columns.length);
    expect(tbody.querySelectorAll('tr td')).toHaveLength(columns.length);
  });

  it('reads the per-question keys the server flattens', () => {
    const columns = responseColumns(QUESTIONS);
    const cell = (header: string) => columns.find(c => c.header === header)!.cell({
      image_quality_choice: 'A',
      image_quality_preferred_method: 'method_a',
      image_quality_confidence: 4,
    });
    expect(cell('Choice (Image Quality)')).toBe('A');
    expect(cell('Preferred (Image Quality)')).toBe('method_a');
    expect(cell('Conf (Image Quality)')).toBe('4');
  });

  it('adds the configured demographics fields and skips the email field', () => {
    const headers = demographicsColumns({
      demographics: [
        { name: 'email', type: 'email', label: 'Email' },
        { name: 'occupation', type: 'text', label: 'Occupation' },
      ],
    }).map(c => c.header);
    expect(headers).toEqual(['Email', 'Referral', 'Browser', 'OS', 'Screen', 'Occupation', 'Trials']);
  });
});

describe('rendering', () => {
  it('turns a participant-supplied payload into text, never markup', () => {
    const tbody = document.getElementById('results-body')!;
    const columns = responseColumns(QUESTIONS);
    renderRows(tbody, [{
      email: '<img src=x onerror="window.__xss=1">',
      image_quality_choice: '<script>window.__xss=2</script>',
    }], columns);

    expect(tbody.querySelectorAll('*:not(td):not(tr)')).toHaveLength(0);
    expect((window as unknown as { __xss?: number }).__xss).toBeUndefined();
    expect(tbody.textContent).toContain('<img src=x onerror="window.__xss=1">');
  });

  it('marks the dense cells narrow', () => {
    const tbody = document.getElementById('results-body')!;
    renderRows(tbody, [{ email: 'a@b.c' }], responseColumns(QUESTIONS));
    expect(tbody.querySelector('td.cell-narrow')?.textContent).toBeTruthy();
  });

  it("counts a participant's trials as the roster endpoint reported them", () => {
    const trials = demographicsColumns({}).find(c => c.header === 'Trials')!;
    expect(trials.cell({ trials_completed: 5, pairs_per_user: 15 })).toBe('5/15');
  });
});

/* Measured on d1923ec: on a 3,600-answer study /api/admin/results?limit=1200 answers with 1,000 rows
 * (ADMIN_MAX_PAGE_SIZE), and the poll's `state.rows = page.rows` dropped a table paged to 1,200 rows to
 * 1,000 on the first 30s tick — the shedding starts at that cap, so the 400-row test above passes. */
describe('the poll past the server page cap', () => {
  const SERVER_MAX_LIMIT = 1000;
  const PAGE_SIZE = 200;
  const TOTAL = 3600;

  const shown = () => document.getElementById('row-count')!.textContent;
  const settle = async () => { for (let i = 0; i < 8; i += 1) await vi.advanceTimersByTimeAsync(0); };

  it('keeps every row the analyst paged to, and never asks for a page the server will not send', async () => {
    const rows = Array.from({ length: TOTAL }, (_, i) => ({ email: `p${i}@example.com`, image_pair_id: i + 1 }));
    const limits: number[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: unknown) => {
      const target = new URL(String(url), 'http://test');
      let payload: unknown;
      if (target.pathname.startsWith('/api/admin/results')) {
        const asked = Number(target.searchParams.get('limit'));
        limits.push(asked);
        const limit = Math.max(1, Math.min(asked, SERVER_MAX_LIMIT));
        const offset = Number(target.searchParams.get('offset'));
        payload = { rows: rows.slice(offset, offset + limit), total: TOTAL, limit, offset };
      } else if (target.pathname.startsWith('/api/admin/participants')) {
        payload = { rows: [], total: 0, limit: 200, offset: 0, summary: { started: 0, completed: 0 } };
      } else if (target.pathname.startsWith('/api/admin/stats')) {
        payload = { total_responses: TOTAL, preference_by_question: {} };
      } else {
        payload = { survey: { pairs_per_user: 20 }, questions: [] };
      }
      return { ok: true, status: 200, json: async () => payload } as Response;
    }));
    vi.useFakeTimers();
    document.body.innerHTML = `<div data-admin-app>
      <table><thead id="table-header"></thead><tbody id="results-body"></tbody></table>
      <span id="row-count"></span><button id="load-more">Load more</button>
      <button id="toggle-view">Toggle</button>
      <div id="method-pref-cards"></div></div>`;
    vi.resetModules();
    await import('../src/admin');
    await settle();
    document.getElementById('toggle-view')!.click();
    await settle();

    for (let page = 1; page < 1200 / PAGE_SIZE; page += 1) {
      document.getElementById('load-more')!.click();
      await settle();
    }
    expect(shown()).toBe(`Showing 1200 of ${TOTAL} responses`);

    await vi.advanceTimersByTimeAsync(60000);
    await settle();
    expect(shown()).toBe(`Showing 1200 of ${TOTAL} responses`);
    expect(document.querySelectorAll('#results-body tr')).toHaveLength(1200);
    expect(limits).toEqual(limits.map((limit) => Math.min(limit, SERVER_MAX_LIMIT)));

    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
});

describe('formatters', () => {
  it('keeps a non-numeric time_spent from blanking the table', () => {
    expect(formatTimeSpent(12.34)).toBe('12.3');
    expect(formatTimeSpent('legacy text')).toBe('-');
    expect(formatTimeSpent(null)).toBe('-');
  });

  it('summarises preferences and says so when there are none', () => {
    expect(preferenceSummary({ preferences: { image_quality: { method_a: 3, method_b: 1 } } }, 'image_quality'))
      .toBe('method_a: 3, method_b: 1');
    expect(preferenceSummary({ preferences: {} }, 'image_quality')).toBe('No data');
    expect(preferenceSummary(null, 'image_quality')).toBe('No data');
  });
});

describe('the 30s poll and paging', () => {
  const PAGE_SIZE = 200;
  const TOTAL = 400;

  const shown = () => document.getElementById('row-count')!.textContent;
  // A click kicks off a plain promise chain, so the fake clock must be nudged several times to drain it.
  const settle = async () => { for (let i = 0; i < 8; i += 1) await vi.advanceTimersByTimeAsync(0); };

  const ROSTER = Array.from({ length: 250 }, (_unused, i) => ({
    email: `p${i}@example.com`, trials_completed: 20, pairs_per_user: 20,
  }));

  beforeEach(() => {
    const rows = Array.from({ length: TOTAL }, (_, i) => ({
      email: `p${i}@example.com`, image_pair_id: i + 1,
    }));
    vi.stubGlobal('fetch', vi.fn(async (url: unknown) => {
      const target = new URL(String(url), 'http://test');
      const pageOf = (all: Row[]) => {
        const limit = Number(target.searchParams.get('limit'));
        const offset = Number(target.searchParams.get('offset'));
        return { rows: all.slice(offset, offset + limit), total: all.length, limit, offset };
      };
      const payload = target.pathname.startsWith('/api/admin/results')
        ? pageOf(rows)
        : target.pathname.startsWith('/api/admin/participants')
          ? { ...pageOf(ROSTER), summary: { started: 250, completed: 250, pairs_per_user: 20, dropout: {} } }
          : target.pathname.startsWith('/api/admin/stats')
            ? { total_responses: TOTAL, preference_by_question: {} }
            : { survey: { pairs_per_user: PAGE_SIZE }, questions: QUESTIONS };
      return { ok: true, status: 200, json: async () => payload } as Response;
    }));
  });

  it('keeps the rows the analyst paged to after one poll', async () => {
    vi.useFakeTimers();
    document.body.innerHTML = `<div data-admin-app>
      <table><thead id="table-header"></thead><tbody id="results-body"></tbody></table>
      <span id="row-count"></span><button id="load-more">Load more</button>
      <button id="toggle-view">Toggle</button>
      <div id="method-pref-cards"></div></div>`;
    vi.resetModules();
    // The page marker in that markup is what boots the dashboard, exactly as the served page does.
    await import('../src/admin');
    await settle();
    document.getElementById('toggle-view')!.click();
    await settle();
    expect(shown()).toBe(`Showing ${PAGE_SIZE} of ${TOTAL} responses`);

    document.getElementById('load-more')!.click();
    await settle();
    expect(shown()).toBe(`Showing ${TOTAL} of ${TOTAL} responses`);

    await vi.advanceTimersByTimeAsync(30000);
    await settle();
    expect(shown()).toBe(`Showing ${TOTAL} of ${TOTAL} responses`);

    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
});
