// script.js installs tutorial mode at load time when window.TUTORIAL_MODE is set,
// exactly as the inline script in index.html does — so the flag precedes the require.
window.TUTORIAL_MODE = true;

const script = require('../../src/survey/static/script.js');
const {
    CONFIG,
    PAIR,
    answer,
    apiMock,
    flush,
    loadSurvey,
    stubScrolling,
    surveyDom,
} = require('./helpers/survey-env');

const banner = () => document.getElementById('tutorial-banner');
const title = () => document.getElementById('tutorial-title');
const text = () => document.getElementById('tutorial-text');
const nextBtn = () => document.querySelector('.btn-tutorial-primary');
const submitBtn = () => document.getElementById('submit-btn');
const highlighted = () => Array.from(document.querySelectorAll('.tutorial-highlight'));

// index.html starts the tutorial on the window load event, which jsdom fired long ago.
const startTutorial = () => window.dispatchEvent(new Event('load'));

// The step counter lives in the script's module scope, so finish by walking to the end.
const finishTutorial = () => {
    for (let i = 0; i < 10 && banner().style.display !== 'none'; i += 1) {
        window.nextTutorialStep();
    }
};

beforeEach(async () => {
    surveyDom();
    stubScrolling();
    window.tutorialCompleted = false;
    await loadSurvey();
});

describe('tutorial walkthrough', () => {
    test('walks the configured steps, then closes itself', () => {
        startTutorial();

        expect(banner().style.display).toBe('block');
        expect(title().textContent).toBe('Images');
        expect(text().textContent).toBe('Compare A and B');
        expect(highlighted()).toHaveLength(3);
        expect(document.getElementById('tutorial-progress-circle')
            .getAttribute('stroke-dasharray')).toBe('33.33333333333333, 100');
        expect(submitBtn().disabled).toBe(true);
        expect(submitBtn().title).toBe('Complete the tutorial first');

        window.nextTutorialStep();
        // 'auto_questions' expands to one step per configured question.
        expect(title().textContent).toBe('Image quality');
        expect(text().innerHTML).toBe('<strong>Which image is better?</strong>');
        expect(highlighted()).toHaveLength(1);
        expect(highlighted()[0]).toBe(document.querySelector('.questions-container'));

        window.nextTutorialStep();
        expect(title().textContent).toBe('Mask');
        expect(highlighted()[0]).toBe(document.querySelector('.questions-container'));
        expect(nextBtn().textContent).toBe('Got it!');
        expect(document.getElementById('tutorial-checkmark').classList.contains('show')).toBe(true);

        window.nextTutorialStep();
        window.nextTutorialStep();
        window.nextTutorialStep();
        expect(banner().style.display).toBe('none');
        expect(highlighted()).toHaveLength(0);
        expect(window.tutorialCompleted).toBe(true);
    });

    test('submit stays locked until the tutorial ends, then respects the answers', () => {
        script.setupSubmitValidation();
        startTutorial();

        answer('image_choice', 'A');
        answer('image_confidence', '3');
        answer('mask_choice', 'A');
        answer('mask_confidence', '3');
        expect(submitBtn().disabled).toBe(true);

        finishTutorial();

        expect(submitBtn().disabled).toBe(false);
    });

    test('a study without tutorial steps gets a single placeholder step', async () => {
        await loadSurvey({ ...CONFIG, tutorial: {} });

        startTutorial();

        expect(title().textContent).toBe('Tutorial');
        expect(text().textContent).toBe('No tutorial steps configured.');
        expect(highlighted()).toHaveLength(0);
    });

    test('the tutorial page loads its first pair like the real survey does', async () => {
        global.fetch = apiMock({ '/api/get_image_pair': PAIR });

        await script.loadImagePair(0);
        await flush();

        expect(document.getElementById('image-a').src).toBe('https://img/a.png');
    });
});
