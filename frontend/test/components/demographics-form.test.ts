// @vitest-environment jsdom
import { beforeEach, describe, expect, test, vi } from 'vitest';

import { mountDemographicsForm } from '../../src/components/demographics-form';
import type { DemographicsFormProps } from '../../src/components/demographics-form';
import { createSurveyApi } from '../../src/lib/session-api';
import type { DeviceInfo } from '../../src/lib/device-info';
import { fakeApi } from '../helpers/api';

const DEVICE = {
    browser: 'Chrome',
    browser_version: '120',
    os: 'macOS',
    screen_width: 1512,
    screen_height: 982,
    pixel_ratio: 2,
    color_depth: 30,
    viewport_width: 1280,
    viewport_height: 900,
} satisfies DeviceInfo;

const FORM = `<form id="demographics-form">
    <input name="email" value="a@b.c" />
    <input name="age" value="30" />
    <input type="checkbox" name="interests[]" value="design" checked />
    <input type="checkbox" name="interests[]" value="code" checked />
    <button type="submit" id="demo-submit">Submit</button>
</form>`;

type Harness = {
    form: HTMLFormElement;
    submitButton: HTMLButtonElement;
    posts: () => Record<string, unknown>[];
    props: DemographicsFormProps;
    rebind: (over: Partial<DemographicsFormProps>) => Mount;
    ask: ReturnType<typeof vi.fn>;
    accepted: ReturnType<typeof vi.fn>;
    declined: ReturnType<typeof vi.fn>;
    shown: ReturnType<typeof vi.fn>;
};

type Mount = ReturnType<typeof mountDemographicsForm>;

function harness(routes: Record<string, unknown>) {
    document.body.innerHTML = FORM;
    const form = document.getElementById('demographics-form') as HTMLFormElement;
    const api = fakeApi(routes as never);
    const props: DemographicsFormProps = {
        api: createSurveyApi(api.fetch),
        banner: { show: vi.fn(), hide: vi.fn(), dispose: vi.fn() },
        retake: { ask: vi.fn(async () => true), dispose: vi.fn() },
        deviceInfo: DEVICE,
        checkboxFields: () => ['interests'],
        onAccepted: vi.fn(),
        onDeclinedRetake: vi.fn(),
    };

    let mounted: Mount = mountDemographicsForm(form, props);
    // One listener at a time: a second mount on the same form would post twice and hide the
    // behaviour the rebinding tests are about.
    const rebind = (over: Partial<DemographicsFormProps>): Mount => {
        mounted.dispose();
        mounted = mountDemographicsForm(form, { ...props, ...over });
        return mounted;
    };

    const posts = () =>
        api.calls.map((call) => JSON.parse(String(call.options?.body)) as Record<string, unknown>);
    return {
        form,
        submitButton: document.getElementById('demo-submit') as HTMLButtonElement,
        posts,
        props,
        rebind,
        ask: props.retake.ask as unknown as ReturnType<typeof vi.fn>,
        accepted: props.onAccepted as unknown as ReturnType<typeof vi.fn>,
        declined: props.onDeclinedRetake as unknown as ReturnType<typeof vi.fn>,
        shown: props.banner.show as unknown as ReturnType<typeof vi.fn>,
        api,
    };
}

const submit = (h: Harness) => h.form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
const flush = () => new Promise((resolve) => { setTimeout(resolve, 0); });

describe('DemographicsForm', () => {
    let h: Harness;

    beforeEach(() => {
        h = harness({ '/api/submit_demographics': { success: true } });
    });

    test('posts the normalised form with the device snapshot', async () => {
        await submit(h);
        await flush();

        expect(h.posts()).toHaveLength(1);
        expect(h.posts()[0]).toMatchObject({
            email: 'a@b.c',
            age: '30',
            interests: 'design, code',
            device_info: DEVICE,
        });
    });

    // The model's contract: unchecked boxes submit nothing, and an absent key reads as
    // "skipped" in the analysis export, so a declared field posts the literal 'none'.
    test('a declared checkbox field that is unchecked posts none, not a missing key', async () => {
        for (const box of Array.from(h.form.querySelectorAll<HTMLInputElement>('input[type="checkbox"]'))) {
            box.checked = false;
        }

        await submit(h);
        await flush();

        expect(h.posts()[0].interests).toBe('none');
    });

    test('a plain success navigates and never asks about retaking', async () => {
        await submit(h);
        await flush();

        expect(h.ask).not.toHaveBeenCalled();
        expect(h.accepted).toHaveBeenCalledTimes(1);
    });

    test('the submit is cancelable: the browser must not do a form navigation', async () => {
        const event = new Event('submit', { bubbles: true, cancelable: true });
        h.form.dispatchEvent(event);
        await flush();

        expect(event.defaultPrevented).toBe(true);
    });

    test('a returning participant who declines leaves for the survey untouched', async () => {
        h = harness({ '/api/submit_demographics': { success: true, is_retaking: true } });
        h.ask.mockResolvedValueOnce(false);

        await submit(h);
        await flush();

        expect(h.ask).toHaveBeenCalledTimes(1);
        expect(h.posts()).toHaveLength(1);
        expect(h.declined).toHaveBeenCalledTimes(1);
        expect(h.accepted).not.toHaveBeenCalled();
    });

    test('confirming the retake re-posts with the confirmation flag', async () => {
        h = harness({ '/api/submit_demographics': { success: true, is_retaking: true } });

        await submit(h);
        await flush();

        expect(h.posts()).toHaveLength(2);
        expect(h.posts()[0]).not.toHaveProperty('confirm_retake');
        expect(h.posts()[1]).toMatchObject({ confirm_retake: true, email: 'a@b.c' });
        expect(h.accepted).toHaveBeenCalledTimes(1);
    });

    test('a retake confirmation the server refuses does not navigate', async () => {
        h = harness({
            '/api/submit_demographics': (options?: RequestInit) =>
                String(options?.body).includes('confirm_retake')
                    ? { success: false, error: 'nope' }
                    : { success: true, is_retaking: true },
        });

        await submit(h);
        await flush();

        expect(h.accepted).not.toHaveBeenCalled();
        expect(h.shown).toHaveBeenCalledWith('Failed to submit demographics. Please try again.');
    });

    test('an http failure shows the failure banner', async () => {
        h = harness({ '/api/submit_demographics': { ok: false, status: 500, error: 'boom' } });

        await submit(h);
        await flush();

        expect(h.shown).toHaveBeenCalledWith('Failed to submit demographics. Please try again.');
        expect(h.accepted).not.toHaveBeenCalled();
    });

    test('a network failure shows the network banner', async () => {
        const form = h.form;
        const disconnected = createSurveyApi(vi.fn(async () => {
            throw new TypeError('Failed to fetch');
        }) as unknown as typeof fetch);

        h.rebind({ api: disconnected });
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        await flush();

        expect(h.shown).toHaveBeenCalledWith('Network error. Please check your connection and try again.');
    });

    test('a second submit while the first is open is dropped, and the button comes back', async () => {
        let release: () => void = () => {};
        const gate = new Promise<void>((resolve) => { release = resolve; });
        const posts: string[] = [];
        const slow = createSurveyApi(vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
            posts.push(String(options?.body));
            await gate;
            return { ok: true, status: 200, json: async () => ({ success: true }) } as Response;
        }) as unknown as typeof fetch);
        h.rebind({ api: slow });

        await submit(h);
        await submit(h);
        expect(posts).toHaveLength(1);
        expect(h.submitButton.disabled).toBe(true);

        release();
        await flush();
        await flush();

        expect(posts).toHaveLength(1);
        expect(h.accepted).toHaveBeenCalledTimes(1);
        expect(h.submitButton.disabled).toBe(false);
    });

    test('dispose stops the form from submitting', async () => {
        const api = fakeApi({ '/api/submit_demographics': { success: true } } as never);
        const live = h.rebind({ api: createSurveyApi(api.fetch) });
        live.dispose();

        await submit(h);
        await flush();

        expect(api.calls).toHaveLength(0);
        expect(h.accepted).not.toHaveBeenCalled();
    });
});
