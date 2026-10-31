// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { mountQuestionFlow } from '../../src/components/question-flow';
import { surveyFixture } from '../helpers/dom';
import type { QuestionConfig, Trial } from '../../src/study-state';

// A name like this is a legal HTML id and an illegal CSS selector, which is the whole finding.
const NAME = 'quality (1-5)';

const QUESTIONS: QuestionConfig[] = [{ name: NAME, label: 'Quality', type: 'ab_preference' }];
const TRIAL = { id: 1, prompt: 'p', total_pairs: 1 } as Trial;

function mount() {
    return mountQuestionFlow(document.getElementById('survey-section') as HTMLElement, {
        form: document.getElementById('survey-form') as HTMLFormElement,
        submitButton: document.getElementById('submit-btn') as HTMLButtonElement,
        blocksSubmit: () => false,
        questions: () => QUESTIONS,
        inputs: () => [],
        viewport: () => ({ width: 1280, height: 900 }),
        autoAdvanceDelayMs: 0,
        observeSections: (_sections, onVisible) => {
            onVisible(0);
            return { dispose: vi.fn() };
        },
    });
}

describe('a question name the page cannot write as a selector', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        surveyFixture();
        document.querySelector('.questions-container')!.innerHTML =
            `<div id="${NAME}-evaluation" class="evaluation-section" style="display:none">
               <div class="radio-group">
                 <input type="radio" name="${NAME}_choice" id="q-a" value="A"><label for="q-a">A</label>
                 <input type="radio" name="${NAME}_choice" id="q-b" value="B"><label for="q-b">B</label>
               </div>
             </div>`;
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    test('the trial shows the section, names it visible, and lets Submit gate on it', () => {
        const submit = document.getElementById('submit-btn') as HTMLButtonElement;
        const flow = mount();

        flow.showTrial(TRIAL);

        expect(document.getElementById(`${NAME}-evaluation`)!.style.display).toBe('block');
        expect(flow.visibleSections()).toEqual([NAME]);
        expect(submit.disabled).toBe(true);

        (document.getElementById('q-a') as HTMLInputElement).checked = true;
        flow.validate();
        expect(submit.disabled).toBe(false);

        flow.dispose();
    });
});
