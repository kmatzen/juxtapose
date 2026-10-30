// script.js gates Submit on the walkthrough; the walkthrough itself is covered by components/tutorial-banner.test.ts.
const {
    PAIR,
    answer,
    apiMock,
    loadSurvey,
    seam,
    stubLocation,
    submit,
    flush,
} = require('./helpers/survey-env');

let script;

beforeEach(async () => {
    location = stubLocation();
    jest.resetModules();
    script = require('../../src/survey/static/script.js');
    await loadSurvey();
    script.setupSubmitValidation();
});

const allAnswered = () => {
    answer('image_choice', 'A');
    answer('image_confidence', '3');
    answer('mask_choice', 'A');
    answer('mask_confidence', '3');
};

const submitBtn = () => document.getElementById('submit-btn');

const posts = (url) =>
    global.fetch.mock.calls.some((call) => String(call[0]).startsWith(url));

describe("the walkthrough's gate on Submit", () => {
    test('an unfinished walkthrough keeps a fully answered form disabled', () => {
        seam().setTutorial(false);
        allAnswered();

        expect(submitBtn().disabled).toBe(true);
        expect(submitBtn().title).toBe('Complete the tutorial first');
    });

    test('finishing the walkthrough re-enables the answered form', () => {
        seam().setTutorial(false);
        allAnswered();

        seam().setTutorial(true);
        document.dispatchEvent(new Event('jx:tutorial-complete'));

        expect(submitBtn().disabled).toBe(false);
        expect(submitBtn().title).toBe('');
    });

    test('a page with no walkthrough gates on answers alone', async () => {
        expect(seam().tutorial).toBeNull();
        global.fetch = apiMock({
            '/api/get_image_pair': PAIR,
            '/api/submit_survey': { success: true, completed: true },
        });

        await script.loadImagePair(0);
        allAnswered();
        expect(submitBtn().disabled).toBe(false);

        script.setupEventListeners();
        submit('survey-form');
        await flush();
        expect(posts('/api/submit_survey')).toBe(true);
    });

    // The submit branch keys on tutorial mode, not on completion: a tutorial page never posts a
    // real response, so a finished walkthrough only unlocks the button that ends the tutorial.
    test('a finished walkthrough submits through the tutorial path, never as a response', async () => {
        seam().setTutorial(true);
        global.fetch = apiMock({
            '/api/get_image_pair': PAIR,
            '/api/submit_survey': { success: true, completed: true },
        });

        await script.loadImagePair(0);
        allAnswered();
        expect(submitBtn().disabled).toBe(false);

        script.setupEventListeners();
        submit('survey-form');
        await flush();
        expect(posts('/api/complete_tutorial')).toBe(true);
        expect(posts('/api/submit_survey')).toBe(false);
        expect(location.href).toBe('/');
    });
});
