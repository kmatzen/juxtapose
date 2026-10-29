// Audit #5 regression, run against the real script.js via require() so coverage counts the real code.
const path = require('path');

const SCRIPT_PATH = path.join(__dirname, '../../src/survey/static/script.js');
const script = require(SCRIPT_PATH);

const SURVEY_CONFIG = {
    dev_mode: false,
    inputs: [
        { name: 'source_image', type: 'image', column: 'image_url' },
        { name: 'mask', type: 'image', column: 'mask_url' }
    ],
    questions: [
        { name: 'image', label: 'Which image is better?', type: 'ab_preference', required: true },
        { name: 'mask', label: 'Which mask matches?', type: 'ab_preference', required: true, depends_on: 'mask' }
    ]
};

function buildForm() {
    document.body.innerHTML = `
        <form id="survey-form">
            <div class="questions-container">
                <div id="image-evaluation" class="evaluation-section">
                    <input type="radio" name="image_choice" value="A">
                    <input type="radio" name="image_choice" value="B">
                    <input type="radio" name="image_confidence" value="3">
                </div>
                <div id="mask-evaluation" class="evaluation-section">
                    <input type="radio" name="mask_choice" value="A">
                    <input type="radio" name="mask_choice" value="B">
                    <input type="radio" name="mask_confidence" value="3">
                </div>
            </div>
            <button type="submit" id="submit-btn" disabled>Submit</button>
        </form>
    `;
}

function answer(name, value) {
    const radio = document.querySelector(`input[name="${name}"][value="${value}"]`);
    if (!radio) throw new Error(`no radio ${name}=${value}`);
    radio.checked = true;
    radio.dispatchEvent(new Event('change', { bubbles: true }));
}

function answerImageQuestions() {
    answer('image_choice', 'A');
    answer('image_confidence', '3');
}

const submitBtn = () => document.getElementById('submit-btn');
const maskSection = () => document.getElementById('mask-evaluation');

describe('hidden optional section does not lock submit (audit #5)', () => {
    beforeEach(async () => {
        buildForm();
        global.fetch = jest.fn(() =>
            Promise.resolve({ ok: true, json: () => Promise.resolve(SURVEY_CONFIG) })
        );
        await script.checkDevMode();
        script.setupSubmitValidation();
    });

    test('empty mask column hides the mask section', () => {
        script.updateQuestionVisibility({ image_url: 'a.png', mask_url: '' });
        expect(maskSection().style.display).toBe('none');
    });

    test('submit enables after answering only the visible questions', () => {
        script.updateQuestionVisibility({ image_url: 'a.png', mask_url: '' });
        answerImageQuestions();
        expect(submitBtn().disabled).toBe(false);
    });

    test('submit still gates on a visible mask section', () => {
        script.updateQuestionVisibility({ image_url: 'a.png', mask_url: 'm.png' });
        answerImageQuestions();
        expect(maskSection().style.display).toBe('block');
        expect(submitBtn().disabled).toBe(true);

        answer('mask_choice', 'B');
        answer('mask_confidence', '3');
        expect(submitBtn().disabled).toBe(false);
    });

    test('radios outside any section stay required', () => {
        document.getElementById('survey-form').insertAdjacentHTML(
            'afterbegin',
            '<input type="radio" name="outside_choice" value="A">'
        );
        script.updateQuestionVisibility({ image_url: 'a.png', mask_url: '' });
        answerImageQuestions();
        expect(submitBtn().disabled).toBe(true);

        answer('outside_choice', 'A');
        expect(submitBtn().disabled).toBe(false);
    });
});
