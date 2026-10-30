import { vi } from 'vitest';

import type { StudyConfig, Trial } from '../../src/study-state';

export const CONFIG: StudyConfig = {
    dev_mode: false,
    inputs: [
        { name: 'mask', type: 'image', column: 'mask_url', label: 'Spatial Mask' },
        { name: 'identity', type: 'image_gallery', column: 'identity_urls', label: 'Reference' },
    ],
    outputs: [{ name: 'image', type: 'image', column_a: 'image_a_url', column_b: 'image_b_url' }],
    questions: [
        { name: 'image', label: 'Which image is better?', type: 'ab_preference', confidence: true, section_label: 'Image quality' },
        { name: 'mask', label: 'Which mask matches?', type: 'ab_preference', confidence: true, depends_on: 'mask', section_label: 'Mask' },
    ],
    demographics: [
        { name: 'email', type: 'email', label: 'Email' },
        { name: 'occupation', type: 'text', label: 'Occupation' },
        { name: 'tools', type: 'checkbox', label: 'Tools used' },
    ],
    tutorial: { steps: [{ title: 'Images', text: 'Compare A and B', highlight: '.tile-image' }, 'auto_questions'] },
};

export const PAIR: Trial = {
    id: 7,
    prompt: 'a red cube',
    method_a: 'MethodA',
    method_b: 'MethodB',
    image_a_url: 'https://img/a.png',
    image_b_url: 'https://img/b.png',
    identity_urls: 'https://img/id1.png,https://img/id2.png',
    mask_url: 'https://img/mask.png',
    was_randomized: true,
    total_pairs: 3,
};

export type Reply = { ok?: boolean; status?: number; json?: unknown } & Record<string, unknown>;

export type Routes = Record<string, Reply | ((options?: RequestInit) => Reply)>;

export type FakeApi = ReturnType<typeof fakeApi>;

/** Route prefix -> response, and a loud failure on anything unmocked: a silent default hides drift. */
export function fakeApi(routes: Routes) {
    const calls: { url: string; options?: RequestInit }[] = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
        const url = String(input);
        calls.push({ url, options });
        const key = Object.keys(routes).find((k) => url === k || url.startsWith(k));
        if (!key) throw new Error(`unmocked fetch: ${url}`);
        const route = routes[key];
        const reply = typeof route === 'function' ? route(options) : route;
        const { ok = true, status = 200, json, ...rest } = reply;
        const body = json === undefined ? rest : json;
        return {
            ok,
            status,
            json: async () => body,
        } as Response;
    });
    return { fetch: fetchImpl as unknown as typeof fetch, calls };
}
