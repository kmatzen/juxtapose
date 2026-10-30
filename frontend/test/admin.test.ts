import { beforeEach, describe, expect, it } from 'vitest';

import {
  demographicsColumns,
  formatTimeSpent,
  groupParticipants,
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
    expect(headers).toEqual(['Email', 'Referral', 'Browser', 'OS', 'Screen', 'Occupation', 'Responses']);
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

  it('renders one row per participant with a counted response total', () => {
    const rows: Row[] = [
      { email: 'a@b.c', image_pair_id: 1 },
      { email: 'a@b.c', image_pair_id: 2 },
      { email: 'c@d.e', image_pair_id: 1 },
    ];
    const grouped = groupParticipants(rows, 4);
    expect(grouped).toHaveLength(2);
    expect(grouped[0].responseCount).toBe(2);
    expect(demographicsColumns({}).map(c => c.header)).toContain('Responses');
    const responses = demographicsColumns({}).find(c => c.header === 'Responses')!;
    expect(responses.cell(grouped[0])).toBe('2/4');
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
