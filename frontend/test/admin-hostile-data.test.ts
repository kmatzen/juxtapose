// Issue #25 guard: the roster writes cells with textContent, so this fails the moment a cell, header, or card goes back through innerHTML.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Row } from '../src/admin';

const IMG = '<img src=x onerror="window.__pwned = 1">';
const SCRIPT = '<script>window.__pwned = 1</script>';
const LABEL = '<b>Occupation</b>';

const PARTICIPANT = {
    email: IMG,
    referral_code: SCRIPT,
    consent: 'yes',
    browser: IMG,
    browser_version: '1',
    os: IMG,
    occupation: IMG,
    trials_completed: 20,
    pairs_per_user: 20,
    responses: 20,
} satisfies Row;

function stubFetch(demographicsLabel: string): void {
    vi.stubGlobal('fetch', vi.fn(async (url: unknown) => {
        const target = new URL(String(url), 'http://test');
        const payload = target.pathname.startsWith('/api/admin/participants')
            ? { rows: [PARTICIPANT], total: 1, limit: 1000, offset: 0, summary: { started: 1, completed: 1 } }
            : target.pathname.startsWith('/api/admin/stats')
                ? { participants: 1, avg_confidence: null, avg_time: null, preferences: {} }
                : {
                    survey: { pairs_per_user: 20 },
                    questions: [],
                    demographics: [{ name: 'occupation', label: demographicsLabel, type: 'text' }],
                };
        return { ok: true, status: 200, json: async () => payload } as Response;
    }));
}

async function bootDashboard(): Promise<void> {
    document.body.innerHTML = `<div data-admin-app>
      <table><thead id="table-header"></thead><tbody id="results-body"></tbody></table>
      <span id="row-count"></span><button id="load-more">Load more</button>
      <div id="method-pref-cards"></div></div>`;
    vi.resetModules();
    await import('../src/admin');
    for (let i = 0; i < 8; i += 1) await vi.advanceTimersByTimeAsync(0);
}

describe('the roster against stored payloads (issue #25)', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        delete (window as unknown as Record<string, unknown>).__pwned;
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.unstubAllGlobals();
    });

    it('mounts no element and runs no script from participant-controlled data', async () => {
        stubFetch('Occupation');
        await bootDashboard();

        const body = document.getElementById('results-body')!;
        const cells = document.querySelectorAll('#results-body td');
        expect(cells.length).toBeGreaterThan(0);
        expect(body.querySelector('img, script, iframe, svg')).toBeNull();
        expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined();
        expect(body.textContent).toContain('onerror=');
    });

    it('renders the payload as the literal text the admin must be able to read', async () => {
        stubFetch('Occupation');
        await bootDashboard();

        const occupation = [...document.querySelectorAll('#results-body td')]
            .map(cell => cell.textContent)
            .find(value => value === IMG);
        expect(occupation).toBe(IMG);
    });

    it('treats a study-config label as text too, so a bad config cannot inject markup', async () => {
        stubFetch(LABEL);
        await bootDashboard();

        const header = document.getElementById('table-header')!;
        expect(header.querySelector('b')).toBeNull();
        expect([...header.querySelectorAll('th')].map(th => th.textContent)).toContain(LABEL);
    });
});
