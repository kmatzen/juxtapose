// `fetch` is injected: components take a fake api in tests instead of patching a global.

import type { StudyConfig, Trial } from '../study-state';

export type ApiResult<T> = { ok: boolean; status: number; body: T };

export type DemographicsPayload = Record<string, unknown> & {
    device_info?: Record<string, unknown>;
    confirm_retake?: boolean;
};

export type DemographicsReply = {
    success?: boolean;
    is_retaking?: boolean;
    submitted?: boolean;
    error?: string;
};

export type SurveyReply = { success?: boolean; completed?: boolean; error?: string };

export type PairReply = Trial & { error?: string };

export type SurveyConfig = StudyConfig & { dev_mode?: boolean };

export interface SurveyApi {
    config(): Promise<ApiResult<SurveyConfig>>;
    checkDemographics(): Promise<ApiResult<DemographicsReply>>;
    submitDemographics(payload: DemographicsPayload): Promise<ApiResult<DemographicsReply>>;
    imagePair(index: number): Promise<ApiResult<PairReply>>;
    submitSurvey(payload: unknown): Promise<ApiResult<SurveyReply>>;
    completeTutorial(): Promise<ApiResult<Record<string, unknown>>>;
}

export function csrfToken(doc: Document = document): string {
    const meta = doc.querySelector<HTMLMetaElement>('meta[name="csrf-token"]');
    if (meta?.content) return meta.content;
    for (const cookie of doc.cookie.split(';')) {
        const [name, ...rest] = cookie.trim().split('=');
        if (name === 'csrf_token') return decodeURIComponent(rest.join('='));
    }
    return '';
}

// A non-JSON body (proxy error page, empty 204) must not reject: callers branch on `ok`.
async function bodyOf<T>(response: Response): Promise<T> {
    try {
        return (await response.json()) as T;
    } catch {
        return {} as T;
    }
}

export function createSurveyApi(
    fetchImpl: typeof fetch,
    token: () => string = () => csrfToken(),
): SurveyApi {
    const get = async <T>(url: string): Promise<ApiResult<T>> => {
        const response = await fetchImpl(url);
        return { ok: response.ok, status: response.status, body: await bodyOf<T>(response) };
    };

    const post = async <T>(url: string, payload?: unknown): Promise<ApiResult<T>> => {
        const response = await fetchImpl(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': token(),
            },
            body: payload === undefined ? undefined : JSON.stringify(payload),
        });
        return { ok: response.ok, status: response.status, body: await bodyOf<T>(response) };
    };

    return {
        config: () => get<SurveyConfig>('/api/config'),
        checkDemographics: () => get<DemographicsReply>('/api/check_demographics'),
        submitDemographics: (payload) => post<DemographicsReply>('/api/submit_demographics', payload),
        imagePair: (index) => get<PairReply>(`/api/get_image_pair/${index}`),
        submitSurvey: (payload) => post<SurveyReply>('/api/submit_survey', payload),
        completeTutorial: () => post<Record<string, unknown>>('/api/complete_tutorial'),
    };
}
