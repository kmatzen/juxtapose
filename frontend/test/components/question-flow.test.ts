// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { mountQuestionFlow, observeSectionsIn } from '../../src/components/question-flow';
import type { QuestionFlowProps } from '../../src/components/question-flow';
import { surveyFixture, answer } from '../helpers/dom';
import type { InputConfig, QuestionConfig, Trial } from '../../src/study-state';

// A section is a question *group*: the template renders one #<name>-evaluation per entry.
const QUESTIONS: QuestionConfig[] = [
    { name: 'image', label: 'Image', type: 'single_choice' },
    { name: 'mask', label: 'Mask', type: 'single_choice', depends_on: 'mask' },
];
const INPUTS: InputConfig[] = [{ name: 'mask', type: 'image', column: 'mask_url' }];

const trial = (over: Partial<Trial> = {}): Trial =>
    ({ id: 1, prompt: 'p', total_pairs: 2, mask_url: 'https://img/mask.png', ...over }) as Trial;

type Harness = {
    props: QuestionFlowProps;
    flow: ReturnType<typeof mountQuestionFlow>;
    submit: HTMLButtonElement;
    previous: HTMLButtonElement;
    next: HTMLButtonElement;
    container: HTMLElement;
    observed: ((index: number) => void)[];
};

function harness(over: Partial<QuestionFlowProps> = {}): Harness {
    surveyFixture();
    const observed: ((index: number) => void)[] = [];
    const props: QuestionFlowProps = {
        form: document.getElementById('survey-form') as HTMLFormElement,
        submitButton: document.getElementById('submit-btn') as HTMLButtonElement,
        blocksSubmit: () => false,
        questions: () => QUESTIONS,
        inputs: () => INPUTS,
        viewport: () => ({ width: 1280, height: 900 }),
        autoAdvanceDelayMs: 0,
        observeSections: (_sections, onVisible) => {
            observed.push(onVisible);
            return { dispose: vi.fn() };
        },
        ...over,
    };
    const flow = mountQuestionFlow(document.getElementById('survey-section') as HTMLElement, props);
    return {
        props,
        flow,
        submit: props.submitButton,
        previous: document.getElementById('prev-question-btn') as HTMLButtonElement,
        next: document.getElementById('next-question-btn') as HTMLButtonElement,
        container: document.querySelector('.questions-container') as HTMLElement,
        observed,
    };
}

const section = (id: string) => document.getElementById(id) as HTMLElement;

describe('QuestionFlow', () => {
    let h: Harness;

    beforeEach(() => {
        vi.useFakeTimers();
        h = harness();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    test('a trial without a mask hides the mask questions', () => {
        h.flow.showTrial(trial({ mask_url: '' }));

        expect(section('mask-evaluation').style.display).toBe('none');
        expect(section('image-evaluation').style.display).toBe('block');
    });

    test('hidden questions do not gate Submit', () => {
        h.flow.showTrial(trial({ mask_url: '' }));
        answer('image_choice', 'A');
        answer('image_confidence', '3');

        expect(h.submit.disabled).toBe(false);
    });

    test('every visible group must be answered', () => {
        h.flow.showTrial(trial());
        answer('image_choice', 'A');
        answer('image_confidence', '3');
        expect(h.submit.disabled).toBe(true);

        answer('mask_choice', 'B');
        answer('mask_confidence', '5');
        expect(h.submit.disabled).toBe(false);
    });

    test('an outside lock keeps an answered form disabled and names itself', () => {
        h = harness({ blocksSubmit: () => true });
        h.flow.showTrial(trial({ mask_url: '' }));
        answer('image_choice', 'A');
        answer('image_confidence', '3');

        expect(h.submit.disabled).toBe(true);
        expect(h.submit.title).toBe('Complete the tutorial first');
    });

    test('the lock releasing re-validates through the completion event', async () => {
        let locked = true;
        h = harness({ blocksSubmit: () => locked });
        h.flow.showTrial(trial({ mask_url: '' }));
        answer('image_choice', 'A');
        answer('image_confidence', '3');
        expect(h.submit.disabled).toBe(true);

        locked = false;
        document.dispatchEvent(new Event('jx:tutorial-complete'));
        expect(h.submit.disabled).toBe(false);
        expect(h.submit.title).toBe('');
    });

    test('a page without question sections is not a crash', () => {
        surveyFixture();
        for (const sectionEl of document.querySelectorAll('.evaluation-section')) sectionEl.remove();
        const flow = mountQuestionFlow(document.getElementById('survey-section') as HTMLElement, {
            form: document.getElementById('survey-form') as HTMLFormElement,
            submitButton: document.getElementById('submit-btn') as HTMLButtonElement,
            blocksSubmit: () => false,
            questions: () => QUESTIONS,
            inputs: () => INPUTS,
        });

        expect(() => flow.showTrial(trial())).not.toThrow();
        expect(() => flow.navigate(1)).not.toThrow();
    });

    test('a radio outside every section still gates Submit', () => {
        const stray = document.createElement('input');
        stray.type = 'radio';
        stray.name = 'stray';
        stray.value = 'x';
        h.props.form.append(stray);

        h.flow.showTrial(trial({ mask_url: '' }));
        answer('image_choice', 'A');
        answer('image_confidence', '3');

        expect(h.submit.disabled).toBe(true);
        stray.checked = true;
        stray.dispatchEvent(new Event('change', { bubbles: true }));
        expect(h.submit.disabled).toBe(false);
    });

    test('a required input in a hidden section stops being required', () => {
        const required = document.createElement('input');
        required.type = 'radio';
        required.name = 'stray';
        required.required = true;
        section('mask-evaluation').append(required);

        h.flow.showTrial(trial({ mask_url: '' }));

        expect(required.required).toBe(false);
    });

    test('navigation walks the sections and clamps at both ends', () => {
        h.flow.showTrial(trial());
        expect(h.flow.index()).toBe(0);
        expect(h.previous.disabled).toBe(true);

        h.next.click();
        expect(h.flow.index()).toBe(1);
        expect(h.previous.disabled).toBe(false);
        expect(h.next.disabled).toBe(true);

        h.next.click();
        expect(h.flow.index()).toBe(1);
    });

    test('scrolling a section into view updates what counts as current', () => {
        h.flow.showTrial(trial());
        h.observed[0](1);

        expect(h.flow.index()).toBe(1);
        expect(h.previous.disabled).toBe(false);
    });

    test('finishing a group advances to the next one after a beat', () => {
        h.flow.showTrial(trial());
        answer('image_choice', 'A');
        answer('image_confidence', '3');
        expect(h.flow.index()).toBe(0);

        vi.runAllTimers();
        expect(h.flow.index()).toBe(1);
    });

    test('finishing the last group reveals Submit instead of advancing', () => {
        const scrolled = vi.fn();
        h.submit.scrollIntoView = scrolled;
        h.flow.showTrial(trial());
        h.observed[0](1);

        answer('mask_choice', 'B');
        answer('mask_confidence', '5');
        vi.runAllTimers();

        expect(scrolled).toHaveBeenCalled();
        expect(h.flow.index()).toBe(1);
    });

    test('an answer in a section the participant is not on does not yank the view', () => {
        h.flow.showTrial(trial());
        h.observed[0](1);

        answer('image_choice', 'A');
        answer('image_confidence', '3');
        vi.runAllTimers();

        expect(h.flow.index()).toBe(1);
    });

    test('a new trial rewinds to the first section', () => {
        h.flow.showTrial(trial());
        h.next.click();
        expect(h.flow.index()).toBe(1);

        h.flow.showTrial(trial());
        expect(h.flow.index()).toBe(0);
    });

    test('the layout gives the questions block 150% of one question', () => {
        const first = section('image-evaluation');
        Object.defineProperty(first, 'offsetHeight', { value: 200, configurable: true });
        Object.defineProperty(window, 'innerHeight', { value: 900, configurable: true });

        h.flow.showTrial(trial());

        expect(document.querySelector('.questions-section')!.getAttribute('style')).toContain('max-height: 300px');
        expect(document.querySelector('#image-a')!.getAttribute('style')).toContain('max-height: 360px');
    });

    test('dispose stops the flow from reacting', async () => {
        h.flow.showTrial(trial());
        h.flow.dispose();

        answer('image_choice', 'A');
        answer('image_confidence', '3');
        vi.runAllTimers();

        expect(h.flow.index()).toBe(0);
        expect(h.submit.disabled).toBe(true);
    });
});

describe('observeSectionsIn', () => {
    test('without IntersectionObserver the flow still works, it just cannot follow scroll', () => {
        const saved = (globalThis as Record<string, unknown>).IntersectionObserver;
        delete (globalThis as Record<string, unknown>).IntersectionObserver;
        const onVisible = vi.fn();

        const observer = observeSectionsIn(null, [], onVisible);
        observer.dispose();

        expect(onVisible).not.toHaveBeenCalled();
        (globalThis as Record<string, unknown>).IntersectionObserver = saved;
    });
});
