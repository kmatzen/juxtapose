import type { SurveyConfig } from './session-api';
import { idSelector } from '../study-state';

export type AutofillEnv = {
    random: () => number;
};

/** mulberry32: the sequence depends only on the seed, so a dev-mode autofill pick cannot move when the draw count shifts. */
export function seededRandom(seed: number): () => number {
    let x = (seed >>> 0) || 0x9e3779b9;
    return () => {
        x = (x + 0x6d2b79f5) >>> 0;
        let t = x;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

const DEV_EMAIL = 'test@example.com';
const DEV_TEXT = 'test';

export function autofillDemographics(host: ParentNode, config: SurveyConfig): void {
    for (const field of config.demographics ?? []) {
        const el = host.querySelector<HTMLElement>(idSelector(field.name)) as HTMLInputElement | null;
        if (!el) continue;

        if (field.type === 'email') el.value = DEV_EMAIL;
        else if (field.type === 'text' || field.type === 'textarea') el.value = DEV_TEXT;
        else if (field.type === 'number') el.value = '0';
        else if (field.type === 'select') {
            if (field.options?.length) el.value = field.options[0].value;
        } else if (field.type === 'radio') {
            if (field.options?.length) check(host, field.name, field.options[0].value);
        } else if (field.type === 'checkbox') {
            // The template names checkbox groups `field[]`, so one value per input.
            for (const option of (field.options ?? []).slice(0, 3)) {
                check(host, `${field.name}[]`, option.value);
            }
        }
    }

    const consent = host.querySelector<HTMLInputElement>('input[name="consent"]');
    if (consent) consent.checked = true;
}

/** Dev mode only: answers the visible question sections. Hidden sections stay empty, as in a real session. */
export function autofillSurvey(host: ParentNode, config: SurveyConfig, env: AutofillEnv): void {
    for (const question of config.questions ?? []) {
        const section = host.querySelector<HTMLElement>(idSelector(`${question.name}-evaluation`));
        if (!section || section.style.display === 'none') continue;

        if (question.type === 'ab_preference') {
            check(section, `${question.name}_choice`, env.random() < 0.5 ? 'A' : 'B');
            if (question.confidence) {
                // The template renders confidence as a fixed 1-5; question.scale belongs to likert only.
                check(section, `${question.name}_confidence`, String(pick(5, env)));
            }
        } else if (question.type === 'likert') {
            check(section, `${question.name}_value`, String(pick(question.scale ?? 5, env)));
        } else if (question.type === 'free_text') {
            const box = section.querySelector<HTMLTextAreaElement>(`textarea[name="${question.name}_text"]`);
            if (box) box.value = 'test response';
        } else if (question.type === 'multiple_choice') {
            const first = section.querySelector<HTMLInputElement>(`input[name="${question.name}_value"]`);
            if (first) first.checked = true;
        }
    }
}

function pick(scale: number, env: AutofillEnv): number {
    return Math.floor(env.random() * scale) + 1;
}

function check(host: ParentNode, name: string, value: string): void {
    const input = host.querySelector<HTMLInputElement>(`input[name="${name}"][value="${value}"]`);
    if (input) input.checked = true;
}
