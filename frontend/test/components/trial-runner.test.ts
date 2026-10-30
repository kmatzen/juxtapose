// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { mountTrialRunner } from '../../src/components/trial-runner';
import type { TrialRunnerProps } from '../../src/components/trial-runner';
import { createSurveyApi } from '../../src/lib/session-api';
import { CONFIG, PAIR, fakeApi } from '../helpers/api';
import type { Routes } from '../helpers/api';
import { surveyFixture, answer } from '../helpers/dom';
import type { SurveyConfig } from '../../src/lib/session-api';

const ROUTES: Routes = {
    '/api/check_demographics': { submitted: true },
    '/api/get_image_pair': { ...PAIR },
    '/api/submit_survey': { success: true, completed: false },
    '/api/complete_tutorial': { success: true },
};

type Harness = {
    props: TrialRunnerProps;
    runner: ReturnType<typeof mountTrialRunner>;
    calls: { url: string; options?: RequestInit }[];
    banner: { show: ReturnType<typeof vi.fn> };
    stimulus: { show: ReturnType<typeof vi.fn> };
    conditioning: { show: ReturnType<typeof vi.fn> };
    questions: { showTrial: ReturnType<typeof vi.fn>; validate: ReturnType<typeof vi.fn>; visible: string[] };
    navigate: ReturnType<typeof vi.fn>;
    body: HTMLElement;
};

function harness(over: { routes?: Routes } & Partial<TrialRunnerProps> = {}): Harness {
    surveyFixture();
    const body = document.body;
    const { routes = ROUTES, ...propsOver } = over;
    const spy = fakeApi(routes);
    const surveyApi = createSurveyApi(spy.fetch, () => 'tok');

    const banner = { show: vi.fn(), hide: vi.fn(), dispose: vi.fn() };
    const stimulus = { show: vi.fn(async () => {}), dispose: vi.fn() };
    const conditioning = { show: vi.fn(), clear: vi.fn(), dispose: vi.fn() };
    const questions = {
        showTrial: vi.fn(),
        validate: vi.fn(),
        layout: vi.fn(),
        navigate: vi.fn(),
        index: () => 0,
        visibleSections: () => questions.visible,
        visible: ['image', 'mask'],
        dispose: vi.fn(),
    };
    const navigate = vi.fn();

    const props: TrialRunnerProps = {
        api: surveyApi,
        config: () => CONFIG as SurveyConfig,
        banner,
        stimulus,
        conditioning,
        questions,
        tutorial: null,
        navigate,
        random: () => 0.1,
        now: () => 10_000,
        devAutofillDelayMs: 500,
        devSurveyDelayMs: 100,
        ...propsOver,
    };

    const runner = mountTrialRunner(body, props);
    return { props, runner, calls: spy.calls, banner, stimulus, conditioning, questions, navigate, body };
}

const el = (id: string) => document.getElementById(id) as HTMLElement;
const posted = (calls: Harness['calls'], url: string) => {
    const call = calls.find((c) => c.url === url);
    return call?.options?.body ? JSON.parse(String(call.options.body)) : undefined;
};

describe('TrialRunner', () => {
    let h: Harness;

    beforeEach(() => {
        vi.useFakeTimers();
        h = harness();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    test('an intake that has not been filled leaves the page where it is', async () => {
        const quiet = harness({ routes: { '/api/check_demographics': { submitted: false } } });
        await quiet.runner.start();

        expect(el('survey-section').classList.contains('active')).toBe(false);
        expect(quiet.calls.map((c) => c.url)).toEqual(['/api/check_demographics']);
    });

    test('a returning participant lands on the first owed pair', async () => {
        await h.runner.start();

        expect(el('demographics-section').classList.contains('active')).toBe(false);
        expect(el('survey-section').classList.contains('active')).toBe(true);
        expect(el('survey-progress').style.display).toBe('block');
        expect(h.calls.map((c) => c.url)).toEqual(['/api/check_demographics', '/api/get_image_pair/0']);
        expect(h.stimulus.show).toHaveBeenCalledWith(expect.objectContaining({ id: 7 }));
        expect(h.conditioning.show).toHaveBeenCalledWith(expect.objectContaining({ id: 7 }));
        expect(h.questions.showTrial).toHaveBeenCalledWith(expect.objectContaining({ id: 7 }));
    });

    test('the pair counters and progress bar follow the server position', async () => {
        await h.runner.loadPair(1);

        expect(el('current-question').textContent).toBe('2');
        expect(el('total-questions').textContent).toBe('3');
        expect(el('progress-bar-fill').style.width).toBe(`${(1 / 3) * 100}%`);
    });

    test('the first pair writes how many pairs the study has', async () => {
        await h.runner.loadPair(0);
        expect(el('total-pairs-text').textContent).toBe('You will see 3 image pairs in total.');

        const single = harness();
        single.calls.length = 0;
        await single.runner.loadPair(0);
        expect(el('total-pairs-text').textContent).toBe('You will see 3 image pairs in total.');
    });

    test('a study with one pair says pair', async () => {
        const solo = harness();
        solo.props.api = createSurveyApi(fakeApi({ '/api/get_image_pair': { ...PAIR, total_pairs: 1 } }).fetch);
        await solo.runner.loadPair(0);

        expect(el('total-pairs-text').textContent).toBe('You will see 1 image pair in total.');
    });

    test('a pair that is not owed ends the session through the index route', async () => {
        h = harness({ routes: { '/api/get_image_pair': { ok: false, status: 404, error: 'done' } } });
        await h.runner.loadPair(0);

        expect(h.navigate).toHaveBeenCalledWith('/');
        expect(h.banner.show).not.toHaveBeenCalled();
    });

    test('a pair request that fails names the fix', async () => {
        h = harness({ routes: { '/api/get_image_pair': { ok: false, status: 500, error: 'boom' } } });
        await h.runner.loadPair(0);

        expect(h.banner.show).toHaveBeenCalledWith('Failed to load image pair. Please refresh the page.');
        expect(h.calls.find((c) => c.url === '/api/get_image_pair/0')).toBeTruthy();
    });

    test('a pair request that never lands says the network is the problem', async () => {
        h = harness({ routes: { '/api/get_image_pair': () => { throw new Error('offline'); } } });
        await h.runner.loadPair(0);

        expect(h.banner.show).toHaveBeenCalledWith('Network error. Please check your connection.');
    });

    test('the walkthrough submits the tutorial, never a response', async () => {
        h = harness({ tutorial: { isComplete: () => false, start() {}, next() {}, dispose() {} } });
        await h.runner.start();
        h.questions.visible = [];

        el('survey-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        await vi.runOnlyPendingTimersAsync();

        expect(h.calls.map((c) => c.url)).toContain('/api/complete_tutorial');
        expect(h.calls.map((c) => c.url)).not.toContain('/api/submit_survey');
        expect(h.navigate).toHaveBeenCalledWith('/');
    });

    test('the walkthrough leaving the write unsent still redirects', async () => {
        h = harness({
            tutorial: { isComplete: () => false, start() {}, next() {}, dispose() {} },
            routes: { '/api/complete_tutorial': () => { throw new Error('offline'); } },
        });
        await h.runner.submit(submitEvent());

        expect(h.navigate).toHaveBeenCalledWith('/');
    });

    test('a response carries the answers, the pair and the CSRF header', async () => {
        await h.runner.loadPair(0);
        answer('image_choice', 'B');
        answer('image_confidence', '4');
        answer('mask_choice', 'A');
        answer('mask_confidence', '2');

        await h.runner.submit(submitEvent());

        expect(posted(h.calls, '/api/submit_survey')).toEqual({
            image_pair_id: 7,
            responses: {
                image: { choice: 'B', confidence: 4 },
                mask: { choice: 'A', confidence: 2 },
            },
            time_spent: null,
        });
        expect(h.calls.find((c) => c.url === '/api/submit_survey')?.options?.headers)
            .toMatchObject({ 'X-CSRFToken': 'tok' });
    });

    test('a question whose section is hidden leaves the payload', async () => {
        await h.runner.loadPair(0);
        answer('image_choice', 'A');
        answer('image_confidence', '3');
        answer('mask_choice', 'B');
        h.questions.visible = ['image'];

        await h.runner.submit(submitEvent());

        expect(posted(h.calls, '/api/submit_survey').responses).toEqual({
            image: { choice: 'A', confidence: 3 },
        });
    });

    test('the pair is timed from the tiles, not from the request', async () => {
        let clock = 1_000;
        h = harness({ now: () => clock });
        await h.runner.loadPair(0);
        clock = 4_000;
        h.runner.tilesSettled(true);
        clock = 9_000;

        await h.runner.submit(submitEvent());

        expect(posted(h.calls, '/api/submit_survey').time_spent).toBe(5);
    });

    test('a pair whose tiles never arrived reports no time', async () => {
        await h.runner.loadPair(0);
        h.runner.tilesSettled(false);

        await h.runner.submit(submitEvent());

        expect(posted(h.calls, '/api/submit_survey').time_spent).toBeNull();
    });

    test('an unfinished study loads the next pair and returns to the top', async () => {
        const scrollTo = vi.fn();
        window.scrollTo = scrollTo as unknown as typeof window.scrollTo;
        await h.runner.loadPair(0);

        await h.runner.submit(submitEvent());

        expect(h.calls.filter((c) => c.url.startsWith('/api/get_image_pair')).map((c) => c.url))
            .toEqual(['/api/get_image_pair/0', '/api/get_image_pair/1']);
        expect(scrollTo).toHaveBeenCalledWith(0, 0);
        expect(h.runner.index()).toBe(1);
    });

    test('the last response closes the study', async () => {
        h = harness({ routes: {
            '/api/get_image_pair': { ...PAIR },
            '/api/submit_survey': { success: true, completed: true },
        } });
        await h.runner.loadPair(0);

        await h.runner.submit(submitEvent());

        expect(h.navigate).toHaveBeenCalledWith('/');
        expect(h.calls.filter((c) => c.url.startsWith('/api/get_image_pair'))).toHaveLength(1);
    });

    test('a rejected response keeps the answers on screen', async () => {
        h = harness({ routes: {
            '/api/get_image_pair': { ...PAIR },
            '/api/submit_survey': { ok: false, status: 500, success: false, error: 'no' },
        } });
        await h.runner.loadPair(0);

        await h.runner.submit(submitEvent());

        expect(h.banner.show).toHaveBeenCalledWith('Failed to submit response. Please try again.');
    });

    test('a submit that never lands asks for a retry', async () => {
        h = harness({ routes: {
            '/api/get_image_pair': { ...PAIR },
            '/api/submit_survey': () => { throw new Error('offline'); },
        } });
        await h.runner.loadPair(0);
        h.banner.show.mockClear();

        await h.runner.submit(submitEvent());

        expect(h.banner.show).toHaveBeenCalledWith('Network error. Please check your connection and try again.');
    });

    test('a new pair starts from blank answers', async () => {
        await h.runner.loadPair(0);
        answer('image_choice', 'A');

        await h.runner.loadPair(1);

        expect((document.querySelector('input[name="image_choice"][value="A"]') as HTMLInputElement).checked).toBe(false);
    });

    test('dev mode answers the visible sections and leaves the hidden ones', async () => {
        h = harness({ config: () => ({ ...CONFIG, dev_mode: true }) as SurveyConfig });
        el('mask-evaluation').style.display = 'none';

        await h.runner.loadPair(0);
        vi.runAllTimers();

        expect((document.querySelector('input[name="image_choice"][value="A"]') as HTMLInputElement).checked).toBe(true);
        expect((document.querySelector('input[name="image_confidence"][value="1"]') as HTMLInputElement).checked).toBe(true);
        expect((document.querySelector('input[name="mask_choice"][value="A"]') as HTMLInputElement).checked).toBe(false);
        expect(h.questions.validate).toHaveBeenCalled();
    });

    test('dev mode fills the intake form once the page settles', async () => {
        h = harness({ config: () => ({ ...CONFIG, dev_mode: true }) as SurveyConfig });

        await h.runner.start();
        vi.runAllTimers();

        expect((el('email') as HTMLInputElement).value).toBe('test@example.com');
        expect((el('occupation') as HTMLInputElement).value).toBe('test');
    });

    test('a real participant gets no auto-fill', async () => {
        await h.runner.start();
        vi.runAllTimers();

        expect((el('email') as HTMLInputElement).value).toBe('a@b.c');
    });

    test('dispose cancels a scheduled dev auto-fill', async () => {
        h = harness({ config: () => ({ ...CONFIG, dev_mode: true }) as SurveyConfig });
        await h.runner.start();
        h.runner.dispose();
        vi.runAllTimers();

        expect((el('email') as HTMLInputElement).value).toBe('a@b.c');
    });

    test('dispose stops the form from submitting twice', async () => {
        await h.runner.loadPair(0);
        h.runner.dispose();

        el('survey-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        await Promise.resolve();

        expect(h.calls.filter((c) => c.url === '/api/submit_survey')).toHaveLength(0);
    });
});

function submitEvent(): Event {
    return new Event('submit', { bubbles: true, cancelable: true });
}
