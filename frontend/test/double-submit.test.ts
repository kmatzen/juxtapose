// @vitest-environment jsdom
import { afterAll, describe, expect, test, vi } from 'vitest';

import { mountTrialRunner } from '../src/components/trial-runner';
import { createSurveyApi } from '../src/lib/session-api';
import { CONFIG } from './helpers/api';
import { surveyFixture, answer } from './helpers/dom';
import type { SurveyConfig } from '../src/lib/session-api';

type Pending = { resolve: (v: unknown) => void };

function delayedApi(delayed: string[], pending: Pending[]) {
    const calls: string[] = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        calls.push(url);
        const body: Record<string, unknown> = url.startsWith('/api/get_image_pair')
            ? { id: Number(url.split('/').pop()), prompt: 'p', method_a: 'A', method_b: 'B',
                image_a_url: 'a.png', image_b_url: 'b.png', total_pairs: 3, trials_remaining: 3 }
            : url === '/api/check_demographics'
                ? { submitted: true }
                : { success: true, completed: false };
        if (delayed.some((d) => url.startsWith(d))) {
            await new Promise<unknown>((resolve) => { pending.push({ resolve }); });
        }
        return { ok: true, status: 200, json: async () => body } as Response;
    });
    return { api: createSurveyApi(fetchImpl as unknown as typeof fetch, () => 'tok'), calls };
}

const report: string[] = [];
afterAll(() => console.log(report.join('\n')));

describe('double click on Submit', () => {
    test('one trial is answered once and the next trial is the next one', async () => {
        surveyFixture();
        const pending: Pending[] = [];
        const { api, calls } = delayedApi(['/api/submit_survey'], pending);
        const runner = mountTrialRunner(document.body, {
            api,
            config: () => CONFIG as SurveyConfig,
            banner: { show: vi.fn(), hide: vi.fn(), dispose: vi.fn() },
            stimulus: { show: vi.fn(async () => {}), isBlocked: () => false, dispose: vi.fn() },
            conditioning: { show: vi.fn(), clear: vi.fn(), dispose: vi.fn() },
            questions: {
                showTrial: vi.fn(), validate: vi.fn(), layout: vi.fn(), navigate: vi.fn(),
                index: () => 0, visibleSections: () => ['image'], dispose: vi.fn(),
            },
            tutorial: null,
            navigate: vi.fn(),
            random: () => 0.1,
            now: () => 10_000,
        });

        await runner.loadPair(0);
        answer('image_choice', 'A');
        const form = document.getElementById('survey-form') as HTMLFormElement;

        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        expect(pending.length, 'clicks that open submits').toBe(pending.length);
        for (const p of pending.splice(0)) p.resolve({ success: true, completed: false });
        await new Promise((r) => setTimeout(r, 0));
        await new Promise((r) => setTimeout(r, 0));

        const submits = calls.filter((c) => c === '/api/submit_survey').length;
        const pairs = calls.filter((c) => c.startsWith('/api/get_image_pair'));
        expect({ submits, pairs }, 'observed').toEqual('SHOW ME');
    });
});
