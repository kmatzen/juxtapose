import { describe, expect, it } from 'vitest';

import { buildTutorialSteps, type StudyConfig } from '../src/study-state';

const CONFIG: StudyConfig = {
    questions: [
        { name: 'image', label: 'Which is better?', type: 'ab_preference', section_label: 'Image quality' },
        { name: 'mask', label: 'Which mask?', type: 'ab_preference', depends_on: 'mask' },
    ],
};

describe('buildTutorialSteps', () => {
    it('falls back to one step when nothing is configured', () => {
        expect(buildTutorialSteps({})).toEqual([
            { title: 'Tutorial', text: 'No tutorial steps configured.', highlight: null },
        ]);
    });

    it('passes an authored step through and defaults its missing text', () => {
        const [step] = buildTutorialSteps({ tutorial: { steps: [{ title: 'Images', highlight: '.tile-image' }] } });
        expect(step).toEqual({ title: 'Images', text: '', highlight: '.tile-image' });
    });

    it('expands auto_questions into one step per question', () => {
        const steps = buildTutorialSteps({ ...CONFIG, tutorial: { steps: ['auto_questions'] } });
        expect(steps.map((s) => s.title)).toEqual(['Image quality', 'Which mask?']);
        expect(steps[0]).toMatchObject({
            text: 'Which is better?',
            emphasis: 'Which is better?',
            highlight: '.questions-container',
            scrollToWithin: '#image-evaluation',
        });
    });

    it('keeps authored steps ahead of the expanded ones', () => {
        const steps = buildTutorialSteps({
            ...CONFIG,
            tutorial: { steps: [{ title: 'Welcome', text: 'Hi' }, 'auto_questions'] },
        });
        expect(steps.map((s) => s.title)).toEqual(['Welcome', 'Image quality', 'Which mask?']);
    });

    it('expands to nothing when the study has no questions', () => {
        expect(buildTutorialSteps({ tutorial: { steps: ['auto_questions'] } })).toEqual([]);
    });
});
