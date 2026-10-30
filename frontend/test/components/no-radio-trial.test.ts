// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { mountQuestionFlow } from '../../src/components/question-flow';
import type { QuestionFlowProps } from '../../src/components/question-flow';
import { surveyFixture, withFreeTextQuestions, answer } from '../helpers/dom';
import type { InputConfig, QuestionConfig, Trial } from '../../src/study-state';

// Submit is gated on visible radio groups, so these fixtures are about which groups are visible.
const FREE_TEXT: QuestionConfig[] = [{ name: 'comment', label: 'Why?', type: 'free_text', required: true }];
const BOTH_BEHIND_MASK: QuestionConfig[] = [
    { name: 'image', label: 'Image', type: 'ab_preference', depends_on: 'mask' },
    { name: 'mask', label: 'Mask', type: 'ab_preference', depends_on: 'mask' },
];
const IMAGE_PLUS_TEXT: QuestionConfig[] = [
    { name: 'image', label: 'Image', type: 'ab_preference', required: true },
    { name: 'mask', label: 'Mask', type: 'ab_preference', depends_on: 'mask' },
    ...FREE_TEXT,
];
const INPUTS: InputConfig[] = [{ name: 'mask', type: 'image', column: 'mask_url' }];

const trial = (over: Partial<Trial> = {}): Trial =>
    ({ id: 1, prompt: 'p', total_pairs: 2, mask_url: '', ...over }) as Trial;

function flowFor(questions: QuestionConfig[], freeTextNames: string[] = []): HTMLButtonElement {
    surveyFixture();
    if (freeTextNames.length) withFreeTextQuestions(freeTextNames);
    const props: QuestionFlowProps = {
        form: document.getElementById('survey-form') as HTMLFormElement,
        submitButton: document.getElementById('submit-btn') as HTMLButtonElement,
        blocksSubmit: () => false,
        questions: () => questions,
        inputs: () => INPUTS,
        viewport: () => ({ width: 1280, height: 900 }),
        autoAdvanceDelayMs: 0,
    };
    const flow = mountQuestionFlow(document.getElementById('survey-section') as HTMLElement, props);
    flow.showTrial(trial());
    return props.submitButton;
}

describe('a trial with no radio buttons to answer', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    test('a free-text-only study can submit', () => {
        const submit = flowFor(FREE_TEXT, ['comment']);

        const box = document.querySelector<HTMLTextAreaElement>('textarea[name="comment_text"]')!;
        box.value = 'because';
        box.dispatchEvent(new Event('change', { bubbles: true }));

        expect(submit.disabled).toBe(false);
    });

    test('a trial whose rating questions are all hidden can submit', () => {
        const submit = flowFor(BOTH_BEHIND_MASK);

        expect(document.getElementById('image-evaluation')!.style.display).toBe('none');
        expect(document.getElementById('mask-evaluation')!.style.display).toBe('none');
        expect(submit.disabled).toBe(false);
    });

    test('a visible radio group still gates Submit', () => {
        const submit = flowFor(IMAGE_PLUS_TEXT);

        expect(submit.disabled).toBe(true);
        answer('image_choice', 'A');
        answer('image_confidence', '4');
        expect(submit.disabled).toBe(false);
    });
});
