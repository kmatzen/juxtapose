import { beforeEach, describe, expect, it } from 'vitest';

import { createSurveyApi, csrfToken } from '../../src/lib/session-api';
import { fakeApi } from '../helpers/api';

const api = (routes: Parameters<typeof fakeApi>[0], token = 'tok') => {
    const { fetch, calls } = fakeApi(routes);
    return { api: createSurveyApi(fetch, () => token), calls };
};

describe('csrfToken', () => {
    beforeEach(() => {
        document.head.innerHTML = '';
        document.cookie = 'csrf_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
    });

    it('prefers the meta tag', () => {
        document.head.innerHTML = '<meta name="csrf-token" content="from-meta">';
        expect(csrfToken()).toBe('from-meta');
    });

    it('falls back to the cookie and decodes it', () => {
        document.cookie = 'csrf_token=a%2Fb';
        expect(csrfToken()).toBe('a/b');
    });

    it('is empty when the page carries neither', () => {
        expect(csrfToken()).toBe('');
    });
});

describe('createSurveyApi', () => {
    it('reads config with a plain GET', async () => {
        const { api: survey, calls } = api({ '/api/config': { dev_mode: true } });
        const result = await survey.config();
        expect(result).toEqual({ ok: true, status: 200, body: { dev_mode: true } });
        expect(calls[0]).toEqual({ url: '/api/config', options: undefined });
    });

    it('posts demographics with JSON and the CSRF header', async () => {
        const { api: survey, calls } = api({ '/api/submit_demographics': { success: true } });
        const result = await survey.submitDemographics({ email: 'a@b.c' });
        expect(result.body.success).toBe(true);
        expect(calls[0].options).toMatchObject({
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': 'tok' },
            body: JSON.stringify({ email: 'a@b.c' }),
        });
    });

    it('sends no body when a POST has none', async () => {
        const { api: survey, calls } = api({ '/api/complete_tutorial': { success: true } });
        await survey.completeTutorial();
        expect(calls[0].options).toMatchObject({ method: 'POST', body: undefined });
    });

    it('addresses a pair by index', async () => {
        const { api: survey, calls } = api({ '/api/get_image_pair/': {} });
        await survey.imagePair(4);
        expect(calls[0].url).toBe('/api/get_image_pair/4');
    });

    it('carries the status so callers can branch on 404', async () => {
        const { api: survey } = api({ '/api/get_image_pair/9': { ok: false, status: 404, error: 'no pair' } });
        const result = await survey.imagePair(9);
        expect(result).toMatchObject({ ok: false, status: 404, body: { error: 'no pair' } });
    });

    it('survives a body that is not JSON, which is what a proxy error page is', async () => {
        const fetchImpl = async () =>
            ({ ok: false, status: 502, json: async () => JSON.parse('<html>bad gateway</html>') }) as Response;
        const result = await createSurveyApi(fetchImpl).config();
        expect(result).toEqual({ ok: false, status: 502, body: {} });
    });

    it('lets a network failure reject, because the caller shows the network error', async () => {
        const fetchImpl = async () => {
            throw new TypeError('Failed to fetch');
        };
        await expect(createSurveyApi(fetchImpl).config()).rejects.toThrow(TypeError);
    });
});
