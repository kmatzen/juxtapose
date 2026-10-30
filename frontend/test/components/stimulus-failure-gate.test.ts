// @vitest-environment jsdom
import { describe, expect, test, vi } from 'vitest';

import { mountQuestionFlow } from '../../src/components/question-flow';
import { mountStimulusView } from '../../src/components/stimulus-view';
import { surveyFixture, answer } from '../helpers/dom';
import type { LoadedImage } from '../../src/lib/image-loader';
import type { InputConfig, QuestionConfig, Trial } from '../../src/study-state';

/** Audit 6 F5, at the seam survey.ts wires: a pair the participant could not see must not be answerable. */

const QUESTIONS: QuestionConfig[] = [{ name: 'image', label: 'Image', type: 'single_choice' }];
const INPUTS: InputConfig[] = [];

const TRIAL = {
    id: 7,
    prompt: 'Which is the better cat?',
    method_a: 'alpha',
    method_b: 'beta',
    image_a_url: 'https://img/a.png',
    image_b_url: 'https://img/b.png',
    total_pairs: 2,
} as Trial;

const NO_IMAGES = 'The images did not load. Refresh the page to answer this pair.';

function page(preload: (url: string) => Promise<LoadedImage>) {
    surveyFixture();
    const stimulus = mountStimulusView(document.body, {
        lightbox: { open: vi.fn(), close: vi.fn(), dispose: vi.fn() },
        banner: { show: vi.fn(), hide: vi.fn(), dispose: vi.fn() },
        onBlockingChange: () => {},
        onSettled: () => {},
        onTrial: () => {},
        preload,
    });
    const submit = document.getElementById('submit-btn') as HTMLButtonElement;
    const flow = mountQuestionFlow(document.getElementById('survey-section') as HTMLElement, {
        form: document.getElementById('survey-form') as HTMLFormElement,
        submitButton: submit,
        blocksSubmit: () => stimulus.failed(),
        blockReason: () => NO_IMAGES,
        questions: () => QUESTIONS,
        inputs: () => INPUTS,
        viewport: () => ({ width: 1280, height: 900 }),
        autoAdvanceDelayMs: 0,
    });
    return { stimulus, flow, submit };
}

describe('a stimulus that never rendered', () => {
    test('a fully answered form stays locked, and says what to do about it', async () => {
        const h = page(async () => ({ ok: false }));
        await h.stimulus.show(TRIAL);
        h.flow.showTrial(TRIAL);

        answer('image', 'A');

        expect(h.stimulus.failed()).toBe(true);
        expect(h.submit.disabled).toBe(true,
            'an answer to a pair nobody saw is submittable, so it enters the study data');
        expect(h.submit.title).toContain('Refresh the page');
    });

    test('the pair that does render is answerable', async () => {
        const h = page(async () => ({ ok: true }));
        await h.stimulus.show(TRIAL);
        h.flow.showTrial(TRIAL);

        answer('image', 'A');

        expect(h.stimulus.failed()).toBe(false);
        expect(h.submit.disabled).toBe(false);
        expect(h.submit.title).toBe('');
    });
});
