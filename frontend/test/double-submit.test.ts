// @vitest-environment jsdom
import { describe, expect, test, vi } from 'vitest';

import { mountTrialRunner } from '../src/components/trial-runner';
import { createSurveyApi } from '../src/lib/session-api';
import { CONFIG } from './helpers/api';
import { surveyFixture, answer, stubScrolling } from './helpers/dom';
import type { SurveyConfig } from '../src/lib/session-api';

/** submit_survey resolves only when the test releases it: an instant fake can never leave two submits open at once. */
function delayedApi(release: { current: () => void }) {
    const calls: string[] = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        calls.push(url);
        const body: Record<string, unknown> = url.startsWith('/api/get_image_pair')
            ? {
                id: Number(url.split('/').pop()), prompt: 'p', method_a: 'A', method_b: 'B',
                image_a_url: 'a.png', image_b_url: 'b.png', total_pairs: 3, trials_remaining: 3,
            }
            : url === '/api/check_demographics'
                ? { submitted: true }
                : { success: true, completed: false };
        if (url === '/api/submit_survey') {
            await new Promise<unknown>((resolve) => { release.current = () => resolve({ success: true, completed: false }); });
        }
        return { ok: true, status: 200, json: async () => body } as Response;
    });
    return { api: createSurveyApi(fetchImpl as unknown as typeof fetch, () => 'tok'), calls };
}

describe('two submits on one trial', () => {
    test('the second one is ignored: one answer stored, no trial skipped', async () => {
        surveyFixture();
        stubScrolling();
        const release: { current: () => void } = { current: () => {} };
        const { api, calls } = delayedApi(release);
        const runner = mountTrialRunner(document.body, {
            api,
            config: () => CONFIG as SurveyConfig,
            banner: { show: vi.fn(), hide: vi.fn(), dispose: vi.fn() },
            stimulus: { show: vi.fn(async () => {}), dispose: vi.fn() },
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
        release.current();
        // The submit's continuation chains into loadPair, which awaits the pair fetch and the tiles.
        for (let i = 0; i < 8; i += 1) await new Promise((resolve) => { setTimeout(resolve, 0); });

        expect(calls.filter((url) => url === '/api/submit_survey')).toHaveLength(1);
        // One advance, to the next pair: a second submit would post twice and jump past pair 1.
        expect(calls.filter((url) => url.startsWith('/api/get_image_pair'))).toEqual([
            '/api/get_image_pair/0', '/api/get_image_pair/1',
        ]);
        expect(runner.index()).toBe(1);
    });
});
