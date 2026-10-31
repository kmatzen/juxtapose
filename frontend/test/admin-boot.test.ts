import { beforeEach, describe, expect, it, vi } from 'vitest';

/** Measured on 156fe69: with /api/config answering 502 the page made one fetch in two minutes, the table
 * stayed empty, and the 30-second poll was never installed, because a rejected init() dies before
 * setInterval - a dashboard opened during a deploy reload is blank, with no reason on it. */
const PAGE = `<div data-admin-app></div>
<div id="total-responses"></div><div id="avg-confidence"></div><div id="avg-time"></div>
<div id="method-pref-cards"></div>
<table><thead id="table-header"></thead><tbody id="results-body"></tbody></table>
<span id="row-count"></span><button id="load-more"></button>`;

function failingFetch(calls: string[]) {
    return vi.fn(async (url: string) => {
        calls.push(String(url));
        return { ok: false, status: 502, json: async () => ({}) } as unknown as Response;
    });
}

describe('admin dashboard first load', () => {
    beforeEach(() => {
        document.body.innerHTML = PAGE;
    });

    it('keeps polling and says the study setup failed when the first config read fails', async () => {
        const calls: string[] = [];
        vi.stubGlobal('fetch', failingFetch(calls));
        vi.useFakeTimers();

        await import('../src/admin');
        await vi.waitFor(() => expect(calls.length).toBeGreaterThan(0));
        await vi.advanceTimersByTimeAsync(120_000);

        const configReads = calls.filter((call) => call.includes('/api/config')).length;
        expect(configReads).toBeGreaterThan(1);                       // the 30 s poll kept trying
        const table = document.getElementById('results-body')!.textContent ?? '';
        expect(table).toMatch(/study setup/i);                          // the blank page said why
        vi.useRealTimers();
        vi.unstubAllGlobals();
    });
});
