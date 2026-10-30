// @vitest-environment jsdom
import { describe, expect, test, vi } from 'vitest';

import { createTutorialBanner } from '../../src/components/tutorial-banner';
import { buildTutorialSteps } from '../../src/study-state';
import type { StudyConfig, TutorialStep } from '../../src/study-state';


const CONFIG = {
    questions: [
        { name: 'image_choice', label: 'Which image is better?', type: 'single_choice', section_label: 'Image quality' },
        { name: 'mask_choice', label: 'Which mask?', type: 'single_choice', section_label: 'Mask' },
    ],
    tutorial: {
        steps: [
            { title: 'Images', text: 'Compare A and B', highlight: '#image-a, #image-b' },
            'auto_questions',
        ],
    },
} as unknown as StudyConfig;

const stepsFor = (config: StudyConfig) => buildTutorialSteps(config);

const SURVEY_PAGE = `
  <div id="tutorial-banner" style="display: none;">
    <h3 id="tutorial-title"></h3>
    <p id="tutorial-text"></p>
    <svg><path id="tutorial-progress-circle" stroke-dasharray="0, 100"/><path id="tutorial-checkmark"/></svg>
    <button class="btn-tutorial btn-tutorial-primary">Next</button>
  </div>
  <div id="image-a" data-tutorial="image_a"></div>
  <div id="image-b" data-tutorial="image_b"></div>
  <div class="questions-container"></div>
  <div id="image_choice-evaluation"></div>
  <div id="mask_choice-evaluation"></div>`;

type Harness = {
    banner: HTMLElement;
    steps: TutorialStep[];
    completed: () => number;
    title: () => string;
    text: () => string;
    next: () => void;
    highlighted: () => Element[];
    component: ReturnType<typeof createTutorialBanner>;
};

function bannerOnPage(config: StudyConfig = CONFIG): Harness {
    // Highlighting is document-scoped, so the page under test lives in the real document.
    document.body.innerHTML = SURVEY_PAGE;
    const done = vi.fn();
    const steps = stepsFor(config);
    const component = createTutorialBanner(document.getElementById('tutorial-banner')!, {
        steps: () => steps,
        onComplete: done,
    });
    const button = document.querySelector<HTMLButtonElement>('.btn-tutorial-primary')!;
    document.getElementById('image_choice-evaluation')!.scrollIntoView = vi.fn();
    document.getElementById('mask_choice-evaluation')!.scrollIntoView = vi.fn();
    return {
        banner: document.getElementById('tutorial-banner')!,
        steps,
        completed: () => done.mock.calls.length,
        title: () => document.getElementById('tutorial-title')!.textContent!,
        text: () => document.getElementById('tutorial-text')!.innerHTML!,
        next: () => button.click(),
        highlighted: () => Array.from(document.querySelectorAll('.tutorial-highlight')),
        component,
    };
}

describe('TutorialBanner', () => {
    test('start shows the banner, the first step, and every highlight', () => {
        const h = bannerOnPage();
        h.component.start();

        expect(h.banner.style.display).toBe('block');
        expect(h.title()).toBe('Images');
        expect(h.text()).toBe('Compare A and B');
        expect(h.highlighted()).toHaveLength(2);
        expect(h.component.isComplete()).toBe(false);
        expect(h.completed()).toBe(0);
    });

    test('the progress ring advances in proportion to the steps', () => {
        const h = bannerOnPage();
        const circle = document.getElementById('tutorial-progress-circle')!;
        h.component.start();
        expect(circle.getAttribute('stroke-dasharray')).toBe('33.33333333333333, 100');
        h.next();
        expect(circle.getAttribute('stroke-dasharray')).toBe('66.66666666666666, 100');
    });

    test('auto_questions expands to one step per question, with the question scrolled into view', () => {
        const h = bannerOnPage();
        h.component.start();
        h.next();

        expect(h.steps.map((s) => s.title)).toEqual(['Images', 'Image quality', 'Mask']);
        expect(h.title()).toBe('Image quality');
        expect(h.text()).toBe('<strong>Which image is better?</strong>');
        expect(h.highlighted()).toHaveLength(1);
        expect(h.highlighted()[0]).toBe(document.querySelector('.questions-container'));
        expect(document.getElementById('image_choice-evaluation')!.scrollIntoView).toHaveBeenCalled();
    });

    test('highlights move with the step instead of accumulating', () => {
        const h = bannerOnPage();
        h.component.start();
        expect(h.highlighted()).toContain(document.getElementById('image-a'));
        h.next();
        expect(h.highlighted()).not.toContain(document.getElementById('image-a'));
    });

    test('the last step changes the button and shows the checkmark', () => {
        const h = bannerOnPage();
        h.component.start();
        expect(document.querySelector('.btn-tutorial-primary')!.textContent).toBe('Next');
        expect(document.getElementById('tutorial-checkmark')!.classList.contains('show')).toBe(false);

        h.next();
        h.next();
        expect(document.querySelector('.btn-tutorial-primary')!.textContent).toBe('Got it!');
        expect(document.getElementById('tutorial-checkmark')!.classList.contains('show')).toBe(true);
    });

    test('finishing hides the banner, clears highlights and reports completion once', () => {
        const h = bannerOnPage();
        h.component.start();
        h.next();
        h.next();
        expect(h.completed()).toBe(0);

        h.next();
        expect(h.banner.style.display).toBe('none');
        expect(h.highlighted()).toHaveLength(0);
        expect(h.component.isComplete()).toBe(true);
        expect(h.completed()).toBe(1);

        h.next();
        expect(h.completed()).toBe(1);
    });

    test('a study with no tutorial steps gets a placeholder and counts as complete', () => {
        const h = bannerOnPage({ questions: [], tutorial: {} } as unknown as StudyConfig);
        h.component.start();

        expect(h.title()).toBe('Tutorial');
        expect(h.text()).toBe('No tutorial steps configured.');
        expect(h.highlighted()).toHaveLength(0);
        h.next();
        expect(h.completed()).toBe(1);
    });

    test('a highlight selector that matches nothing is skipped, not fatal', () => {
        const done = vi.fn();
        document.body.innerHTML = simpleBanner();
        const component = createTutorialBanner(document.getElementById('tutorial-banner')!, {
            steps: () => [{ title: 'X', text: 'y', highlight: '#not-in-the-page' }],
            onComplete: done,
        });
        component.start();
        expect(document.querySelectorAll('.tutorial-highlight')).toHaveLength(0);
        component.next();
        expect(done).toHaveBeenCalledTimes(1);
    });

    test('step text is text: markup in a config string builds no node', () => {
        document.body.innerHTML = simpleBanner();
        const payload = 'Compare <img src=x onerror=alert(1)> <b>these</b>';
        const component = createTutorialBanner(document.getElementById('tutorial-banner')!, {
            steps: () => [{ title: 'X', text: payload }],
            onComplete: vi.fn(),
        });
        component.start();

        expect(document.getElementById('tutorial-text')!.innerHTML).toBe(
            'Compare &lt;img src=x onerror=alert(1)&gt; &lt;b&gt;these&lt;/b&gt;',
        );
        expect(document.querySelector('#tutorial-text img')).toBeNull();
        component.dispose();
    });

    test('dispose stops the button and leaves no highlights behind', () => {
        const h = bannerOnPage();
        h.component.start();
        h.component.dispose();

        expect(h.highlighted()).toHaveLength(0);
        h.next();
        expect(h.title()).toBe('Images');
        expect(h.completed()).toBe(0);
    });
});

function simpleBanner(): string {
    return `<div id="tutorial-banner" style="display: none;">
        <h3 id="tutorial-title"></h3><p id="tutorial-text"></p>
        <svg><path id="tutorial-progress-circle"/><path id="tutorial-checkmark"/></svg>
        <button class="btn-tutorial-primary">Next</button></div>`;
}
