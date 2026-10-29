const {
    answer,
    loadSurvey,
    script,
    stubScrolling,
    surveyDom,
} = require('./helpers/survey-env');

const submitBtn = () => document.getElementById('submit-btn');

function answerEverything() {
    answer('image_choice', 'A');
    answer('image_confidence', '3');
    answer('mask_choice', 'B');
    answer('mask_confidence', '5');
}

beforeEach(async () => {
    surveyDom();
    stubScrolling();
    await loadSurvey();
    script.setupSubmitValidation();
});

describe('submit gating', () => {
    test('submit starts disabled with an empty form', () => {
        expect(submitBtn().disabled).toBe(true);
        expect(window.triggerFormValidation()).toBe(false);
    });

    test('a half answered question group keeps submit disabled', () => {
        answer('image_choice', 'A');
        answer('mask_choice', 'A');
        expect(submitBtn().disabled).toBe(true);
    });

    test('submit enables once every radio group in the form has an answer', () => {
        answerEverything();
        expect(submitBtn().disabled).toBe(false);
        expect(window.triggerFormValidation()).toBe(true);
    });

    test('clearing the last answer of a group disables submit again', () => {
        answerEverything();
        expect(submitBtn().disabled).toBe(false);

        document.querySelectorAll('input[name="mask_confidence"]').forEach(r => { r.checked = false; });

        expect(window.triggerFormValidation()).toBe(false);
        expect(submitBtn().disabled).toBe(true);
    });

    test('the value a radio carries is what the group is answered with', () => {
        answer('image_choice', 'equal');
        answer('image_confidence', '1');
        answer('mask_choice', 'equal');
        answer('mask_confidence', '1');
        expect(submitBtn().disabled).toBe(false);
        expect(document.querySelector('input[name="image_choice"]:checked').value).toBe('equal');
    });

    test('only the survey form is gated', () => {
        document.getElementById('demographics-form')
            .insertAdjacentHTML('beforeend', '<input type="radio" name="demo_choice" value="A">');
        answerEverything();
        expect(submitBtn().disabled).toBe(false);
    });

    test('a form without a submit button is skipped, not fatal', () => {
        document.getElementById('submit-btn').remove();
        expect(() => script.setupSubmitValidation()).not.toThrow();
    });
});

describe('getCSRFToken', () => {
    beforeEach(() => { document.head.innerHTML = ''; });
    afterEach(() => { document.cookie = 'csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'; });

    test('reads the meta tag when the page renders one', () => {
        document.head.innerHTML = '<meta name="csrf-token" content="meta-token">';
        expect(script.getCSRFToken()).toBe('meta-token');
    });

    test('falls back to the csrf_token cookie and decodes it', () => {
        document.cookie = 'csrf_token=a%2Bb';
        expect(script.getCSRFToken()).toBe('a+b');
    });

    test('returns an empty string when the page carries no token', () => {
        expect(script.getCSRFToken()).toBe('');
    });
});
