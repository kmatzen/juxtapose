/** Audit #1: admin table HTML built from participant input, rendered from real admin.js. */

const {
    esc,
    buildDemographicsHeader,
    buildDemographicsRows,
    buildResponsesHeader,
    buildResponsesRows,
    formatTimeSpent,
} = require('../../src/survey/static/admin.js');

const PAYLOAD = '<img src=x onerror="alert(1)">';

function renderInto(html) {
    const tbody = document.createElement('tbody');
    tbody.innerHTML = html;
    document.body.appendChild(tbody);
    return tbody;
}

describe('admin.js esc()', () => {
    test('escapes all markup characters', () => {
        expect(esc('<a href="x">&\'</a>')).toBe(
            '&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;'
        );
    });

    test('renders empty string for null and undefined', () => {
        expect(esc(null)).toBe('');
        expect(esc(undefined)).toBe('');
        expect(esc(0)).toBe('0');
    });
});

describe('demographics view rendering', () => {
    const fields = [
        { name: 'email', type: 'email', label: 'Email' },
        { name: 'occupation', type: 'select', label: 'Occupation' },
        { name: 'notes', type: 'text', label: PAYLOAD },
    ];

    test('an injected email creates no element, only text', () => {
        const html = buildDemographicsRows(
            [{ email: PAYLOAD, responseCount: 3 }], fields, 30
        );
        const tbody = renderInto(html);

        expect(tbody.querySelector('img')).toBeNull();
        expect(tbody.querySelectorAll('*').length).toBeGreaterThan(0);
        expect(tbody.querySelector('td').textContent).toBe(PAYLOAD);
    });

    test('free-text demographics fields are escaped too', () => {
        const html = buildDemographicsRows(
            [{ email: 'a@b.com', notes: PAYLOAD, responseCount: 1 }], fields, 30
        );

        expect(html).not.toContain('<img');
        expect(html).toContain('&lt;img');
    });

    test('field labels from config are escaped', () => {
        const html = buildDemographicsHeader(fields);

        expect(html).not.toContain('<th><img');
        expect(html).toContain('&lt;img');
    });

    test('empty values still render the dash placeholder', () => {
        const html = buildDemographicsRows([{ responseCount: 0 }], [], 30);
        const tbody = renderInto(html);

        expect(tbody.querySelector('td').textContent).toBe('-');
    });
});

describe('responses view rendering', () => {
    const questions = [
        { name: 'image_quality', type: 'ab_preference', confidence: true,
          section_label: 'Image Quality' },
    ];

    test('method names from the trial data file are escaped', () => {
        const html = buildResponsesRows([{
            email: 'a@b.com',
            method_a: PAYLOAD,
            image_quality_choice: 'A',
            image_quality_preferred_method: PAYLOAD,
            image_quality_confidence: 4,
        }], questions);

        expect(html).not.toContain('<img');
        expect(html).toContain('&lt;img');
    });

    test('a non-numeric time_spent renders a dash, not a crash', () => {
        expect(() => buildResponsesRows(
            [{ email: 'a@b.com', time_spent: '3s' }], questions
        )).not.toThrow();

        const tbody = renderInto(buildResponsesRows(
            [{ email: 'a@b.com', time_spent: '3s' }], questions
        ));
        const cells = tbody.querySelectorAll('td');
        expect(cells[cells.length - 1].textContent).toBe('-');
    });

    test('numeric time_spent keeps one decimal', () => {
        expect(formatTimeSpent(12.34)).toBe('12.3');
        expect(formatTimeSpent('12.34')).toBe('12.3');
        expect(formatTimeSpent('abc')).toBe('-');
        expect(formatTimeSpent('')).toBe('-');
        expect(formatTimeSpent(null)).toBe('-');
    });
});
