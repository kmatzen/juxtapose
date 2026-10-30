// Audit 6 F9: the Demographics view shows the server's participant roster, not the participants inside a response page.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { demographicsColumns, participantSummary } from '../src/admin';

const PARTICIPANTS = [
    ...Array.from({ length: 14 }, (_unused, i) => ({ email: `f${i}@lab.example`, trials_completed: 20, responses: 20, pairs_per_user: 20 })),
    ...Array.from({ length: 5 }, (_unused, i) => ({ email: `d${i}@lab.example`, trials_completed: 15, responses: 15, pairs_per_user: 20 })),
    ...Array.from({ length: 11 }, (_unused, i) => ({ email: `e${i}@lab.example`, trials_completed: 1 + (i % 9), responses: 1 + (i % 9), pairs_per_user: 20 })),
];

const SUMMARY = { started: 30, completed: 14, pairs_per_user: 20, dropout: { '15': 5, '1': 2, '2': 2, '3': 1, '4': 1, '5': 1, '6': 1, '7': 1, '8': 1, '9': 1 } };

describe('the participants roster view', () => {
    it("shows a participant's progress as the server counted it, against the study length", () => {
        const trials = demographicsColumns({}).find(column => column.header === 'Trials');

        expect(trials?.cell({ trials_completed: 14, pairs_per_user: 20, responses: 14 })).toBe('14/20');
    });

    it('says who joined, who finished, and where the study loses people', () => {
        expect(participantSummary({ started: 30, completed: 14, pairs_per_user: 20, dropout: { '15': 5, '1': 2 } }))
            .toBe('30 started · 14 completed · 5 stopped at trial 15 · 2 stopped at trial 1');
    });

    it('does not count a person who never opened a trial as stopping at trial 0', () => {
        expect(participantSummary({ started: 4, completed: 0, dropout: { '0': 4 } }))
            .toBe('4 started · 0 completed');
    });

    it('says so when nobody has joined', () => {
        expect(participantSummary(null)).toBe('No participants yet');
        expect(participantSummary({ started: 0 })).toBe('No participants yet');
    });
});

describe('the dashboard boots on the roster', () => {
    const shown = () => document.getElementById('row-count')!.textContent;
    const settle = async () => { for (let i = 0; i < 8; i += 1) await vi.advanceTimersByTimeAsync(0); };

    beforeEach(() => {
        vi.stubGlobal('fetch', vi.fn(async (url: unknown) => {
            const target = new URL(String(url), 'http://test');
            const payload = target.pathname.startsWith('/api/admin/participants')
                ? (() => {
                    const limit = Number(target.searchParams.get('limit'));
                    const offset = Number(target.searchParams.get('offset'));
                    return {
                        rows: PARTICIPANTS.slice(offset, offset + limit),
                        total: PARTICIPANTS.length, limit, offset, summary: SUMMARY,
                    };
                })()
                : target.pathname.startsWith('/api/admin/stats')
                    ? { participants: 30, avg_confidence: 4.2, avg_time: 12, preferences: {} }
                    : { survey: { pairs_per_user: 20 }, questions: [], demographics: [] };
            return { ok: true, status: 200, json: async () => payload } as Response;
        }));
    });

    it('lists every participant with their own progress, not the ones inside a response page', async () => {
        vi.useFakeTimers();
        document.body.innerHTML = `<div data-admin-app>
          <table><thead id="table-header"></thead><tbody id="results-body"></tbody></table>
          <span id="row-count"></span><button id="load-more">Load more</button>
          <div id="method-pref-cards"></div></div>`;
        vi.resetModules();
        await import('../src/admin');
        await settle();

        const rows = document.querySelectorAll('#results-body tr');
        expect(rows).toHaveLength(30);
        expect(rows[0].textContent).toContain('20/20');
        expect(shown()).toContain('30 started · 14 completed · 5 stopped at trial 15');
        expect(shown()).toContain('30 of 30 participants');

        vi.useRealTimers();
        vi.unstubAllGlobals();
    });
});
