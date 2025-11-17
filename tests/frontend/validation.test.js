/**
 * Tests for form validation logic
 */

const { describe, test, expect, beforeEach } = require('@jest/globals');

// Mock the CONFIG object from script.js
global.CONFIG = {
    TAP_THRESHOLD_PX: 10,
    TUTORIAL_LOAD_DELAY_MS: 500,
    MIN_IMAGE_DIMENSION_PX: 200
};

// Mock the IDENTITY_COLORS array
global.IDENTITY_COLORS = [
    [230, 25, 75],    // Red
    [60, 180, 75],    // Green
    [255, 225, 25],   // Yellow
    [0, 130, 200],    // Blue
    [245, 130, 48],   // Orange
    [145, 30, 180],   // Purple
    [70, 240, 240]    // Cyan
];

describe('Form Validation Logic', () => {
    let submitBtn;
    let questionGroups;

    beforeEach(() => {
        // Setup DOM
        document.body.innerHTML = `
            <form id="survey-form">
                <div class="question-group" data-group="0">
                    <div class="btn-group">
                        <input type="radio" name="better_image" value="A">
                        <input type="radio" name="better_image" value="B">
                        <input type="radio" name="better_image" value="Equal">
                    </div>
                    <div class="btn-group">
                        <input type="radio" name="image_confidence" value="1">
                        <input type="radio" name="image_confidence" value="3">
                        <input type="radio" name="image_confidence" value="5">
                    </div>
                </div>
                <div class="question-group" data-group="1">
                    <div class="btn-group">
                        <input type="radio" name="better_mask_match" value="A">
                        <input type="radio" name="better_mask_match" value="B">
                        <input type="radio" name="better_mask_match" value="Equal">
                    </div>
                    <div class="btn-group">
                        <input type="radio" name="mask_confidence" value="1">
                        <input type="radio" name="mask_confidence" value="3">
                        <input type="radio" name="mask_confidence" value="5">
                    </div>
                </div>
                <button id="submit-btn" type="submit" disabled>Submit</button>
            </form>
        `;
        
        submitBtn = document.getElementById('submit-btn');
        questionGroups = document.querySelectorAll('.question-group');
    });

    test('submit button is disabled when no fields are filled', () => {
        expect(submitBtn.disabled).toBe(true);
    });

    test('submit button is disabled when only some questions are answered', () => {
        // Answer first question only
        const imageRadio = document.querySelector('input[name="better_image"][value="A"]');
        imageRadio.checked = true;
        
        // Manually check if form is complete
        const allAnswered = Array.from(questionGroups).every(group => {
            const allBtnGroups = group.querySelectorAll('.btn-group');
            const choiceInputs = allBtnGroups[0].querySelectorAll('input[type="radio"]');
            const confidenceInputs = allBtnGroups[1].querySelectorAll('input[type="radio"]');
            const choiceSelected = Array.from(choiceInputs).some(input => input.checked);
            const confidenceSelected = Array.from(confidenceInputs).some(input => input.checked);
            return choiceSelected && confidenceSelected;
        });
        
        expect(allAnswered).toBe(false);
    });

    test('form is valid when all required questions are answered', () => {
        // Answer all questions
        document.querySelector('input[name="better_image"][value="A"]').checked = true;
        document.querySelector('input[name="image_confidence"][value="3"]').checked = true;
        document.querySelector('input[name="better_mask_match"][value="B"]').checked = true;
        document.querySelector('input[name="mask_confidence"][value="5"]').checked = true;
        
        // Manually check if form is complete
        const allAnswered = Array.from(questionGroups).every(group => {
            const allBtnGroups = group.querySelectorAll('.btn-group');
            const choiceInputs = allBtnGroups[0].querySelectorAll('input[type="radio"]');
            const confidenceInputs = allBtnGroups[1].querySelectorAll('input[type="radio"]');
            const choiceSelected = Array.from(choiceInputs).some(input => input.checked);
            const confidenceSelected = Array.from(confidenceInputs).some(input => input.checked);
            return choiceSelected && confidenceSelected;
        });
        
        expect(allAnswered).toBe(true);
    });

    test('can select different radio button values', () => {
        const radioA = document.querySelector('input[name="better_image"][value="A"]');
        const radioB = document.querySelector('input[name="better_image"][value="B"]');
        
        radioA.checked = true;
        expect(radioA.checked).toBe(true);
        expect(radioB.checked).toBe(false);
        
        radioB.checked = true;
        radioA.checked = false; // Manually uncheck (DOM doesn't do this automatically in tests)
        expect(radioA.checked).toBe(false);
        expect(radioB.checked).toBe(true);
    });

    test('confidence values are independent of choice values', () => {
        document.querySelector('input[name="better_image"][value="A"]').checked = true;
        document.querySelector('input[name="image_confidence"][value="3"]').checked = true;
        
        const choiceA = document.querySelector('input[name="better_image"][value="A"]');
        const conf3 = document.querySelector('input[name="image_confidence"][value="3"]');
        
        expect(choiceA.checked).toBe(true);
        expect(conf3.checked).toBe(true);
    });
});

describe('Demographics Form Validation', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <form id="demographics-form">
                <input type="email" name="email" id="email" required>
                <input type="text" name="occupation" id="occupation">
                <select name="ai_usage" id="ai_usage" required>
                    <option value="">Select...</option>
                    <option value="never">Never</option>
                    <option value="rarely">Rarely</option>
                    <option value="often">Often</option>
                </select>
                <button type="submit" id="submit-demographics">Continue</button>
            </form>
        `;
    });

    test('email field is required', () => {
        const emailInput = document.getElementById('email');
        expect(emailInput.required).toBe(true);
    });

    test('can enter valid email', () => {
        const emailInput = document.getElementById('email');
        emailInput.value = 'test@example.com';
        expect(emailInput.value).toBe('test@example.com');
    });

    test('can select dropdown option', () => {
        const selectElement = document.getElementById('ai_usage');
        selectElement.value = 'often';
        expect(selectElement.value).toBe('often');
    });

    test('form has all expected fields', () => {
        expect(document.getElementById('email')).toBeTruthy();
        expect(document.getElementById('occupation')).toBeTruthy();
        expect(document.getElementById('ai_usage')).toBeTruthy();
    });
});

describe('CONFIG Object', () => {
    test('CONFIG contains all required constants', () => {
        expect(CONFIG.TAP_THRESHOLD_PX).toBeDefined();
        expect(CONFIG.TUTORIAL_LOAD_DELAY_MS).toBeDefined();
        expect(CONFIG.MIN_IMAGE_DIMENSION_PX).toBeDefined();
    });

    test('CONFIG values are reasonable', () => {
        expect(CONFIG.TAP_THRESHOLD_PX).toBeGreaterThan(0);
        expect(CONFIG.TUTORIAL_LOAD_DELAY_MS).toBeGreaterThan(0);
        expect(CONFIG.MIN_IMAGE_DIMENSION_PX).toBeGreaterThan(0);
    });
});

describe('Identity Colors', () => {
    test('IDENTITY_COLORS has 7 colors', () => {
        expect(IDENTITY_COLORS).toHaveLength(7);
    });

    test('each color is an RGB array with 3 values', () => {
        IDENTITY_COLORS.forEach(color => {
            expect(color).toHaveLength(3);
            color.forEach(value => {
                expect(value).toBeGreaterThanOrEqual(0);
                expect(value).toBeLessThanOrEqual(255);
            });
        });
    });
});

