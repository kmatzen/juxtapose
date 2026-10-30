// @vitest-environment jsdom
import { describe, expect, test } from 'vitest';

import { autofillDemographics, autofillSurvey } from '../../src/lib/dev-autofill';
import { CONFIG } from '../helpers/api';
import { surveyFixture } from '../helpers/dom';
import type { SurveyConfig } from '../../src/lib/session-api';

const config = (over: Partial<SurveyConfig> = {}) => ({ ...CONFIG, ...over }) as SurveyConfig;
const checked = (name: string, value: string) =>
    (document.querySelector(`input[name="${name}"][value="${value}"]`) as HTMLInputElement | null)?.checked;
const value = (id: string) => (document.getElementById(id) as HTMLInputElement).value;
const fixed = (n: number) => () => n;

// A radio or checkbox group is filled through its #<field.name> container, as the template renders it.
function inputs(name: string, values: string[], type = 'radio', inside?: HTMLElement): void {
    const host = inside ?? (document.getElementById(name) ?? document.body);
    for (const v of values) {
        const input = document.createElement('input');
        input.type = type;
        input.name = name;
        input.value = v;
        host.append(input);
    }
}

function section(id: string): HTMLElement {
    const el = document.createElement('div');
    el.id = id;
    document.body.append(el);
    return el;
}

describe('dev auto-fill: intake', () => {
    test('every field type gets a value a study run can survive', () => {
        surveyFixture();
        section('seniority');
        section('tools');
        inputs('seniority', ['mid', 'senior']);
        inputs('tools[]', ['mid', 'firefly'], 'checkbox', document.getElementById('tools')!);
        autofillDemographics(document.body, config({
            demographics: [
                { name: 'email', type: 'email', label: 'Email' },
                { name: 'occupation', type: 'text', label: 'Occupation' },
                { name: 'years', type: 'number', label: 'Years' },
                { name: 'ai_usage', type: 'select', label: 'Usage', options: [{ value: 'often', label: 'Often' }] },
                { name: 'seniority', type: 'radio', label: 'Seniority', options: [{ value: 'mid', label: 'Mid' }] },
                { name: 'tools', type: 'checkbox', label: 'Tools', options: [
                    { value: 'dalle', label: 'DALL-E' },
                    { value: 'sd', label: 'SD' },
                    { value: 'mid', label: 'Midjourney' },
                    { value: 'firefly', label: 'Firefly' },
                ] },
            ],
        }));

        expect(value('email')).toBe('test@example.com');
        expect(value('occupation')).toBe('test');
        expect(checked('ai_usage', 'often')).toBeUndefined();
        expect((document.getElementById('ai_usage') as HTMLSelectElement).value).toBe('often');
        expect(checked('seniority', 'mid')).toBe(true);
        expect([checked('tools[]', 'dalle'), checked('tools[]', 'sd'), checked('tools[]', 'mid')]).toEqual([true, true, true]);
        expect(checked('tools[]', 'firefly')).toBe(false);
    });

    test('checkbox groups stop at three', () => {
        surveyFixture();
        section('tools');
        inputs('tools[]', ['mid', 'firefly'], 'checkbox', document.getElementById('tools')!);
        autofillDemographics(document.body, config({
            demographics: [{ name: 'tools', type: 'checkbox', label: 'Tools', options: [
                { value: 'dalle', label: 'a' }, { value: 'sd', label: 'b' },
                { value: 'mid', label: 'c' }, { value: 'firefly', label: 'd' },
            ] }],
        }));

        expect(checked('tools[]', 'firefly')).toBe(false);
    });

    test('consent is ticked, since a dev run has no participant to ask', () => {
        surveyFixture();
        const consent = document.createElement('input');
        consent.type = 'checkbox';
        consent.name = 'consent';
        document.body.append(consent);

        autofillDemographics(document.body, config());

        expect(consent.checked).toBe(true);
    });

    test('a field the page does not render is skipped', () => {
        surveyFixture();
        expect(() => autofillDemographics(document.body, config({
            demographics: [{ name: 'ghost', type: 'text', label: 'Ghost' }],
        }))).not.toThrow();
    });
});

describe('dev auto-fill: survey', () => {
    test('a seeded run is reproducible', () => {
        surveyFixture();
        const seeded = config({ questions: [{ name: 'image', label: 'i', type: 'ab_preference', confidence: true }] });

        autofillSurvey(document.body, seeded, { random: fixed(0.9) });

        expect(checked('image_choice', 'B')).toBe(true);
        expect(checked('image_confidence', '5')).toBe(true);
    });

    test('likert, free text and multiple choice are answered in their own shapes', () => {
        surveyFixture();
        const notes = section('notes-evaluation');
        inputs('quality_value', ['1', '2'], 'radio', section('quality-evaluation'));
        inputs('tags_value', ['style'], 'radio', section('tags-evaluation'));
        const box = document.createElement('textarea');
        box.name = 'notes_text';
        notes.append(box);

        autofillSurvey(document.body, config({
            questions: [
                { name: 'quality', label: 'q', type: 'likert', scale: 5 },
                { name: 'notes', label: 'n', type: 'free_text' },
                { name: 'tags', label: 't', type: 'multiple_choice' },
            ],
        }), { random: fixed(0.0) });

        expect(checked('quality_value', '1')).toBe(true);
        expect(checked('tags_value', 'style')).toBe(true);
        expect(box.value).toBe('test response');
    });

    test('a section the pair cannot answer stays empty', () => {
        surveyFixture();
        (document.getElementById('mask-evaluation') as HTMLElement).style.display = 'none';

        autofillSurvey(document.body, config(), { random: fixed(0.1) });

        expect(checked('mask_choice', 'A')).toBe(false);
        expect(checked('image_choice', 'A')).toBe(true);
    });
});
