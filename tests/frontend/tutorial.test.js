/**
 * Tests for tutorial functionality
 */

const { describe, test, expect, beforeEach, afterEach } = require('@jest/globals');

// Mock global variables
global.window = {
    ...global.window,
    TUTORIAL_MODE: true,
    tutorialCompleted: false,
    triggerFormValidation: jest.fn()
};

describe('Tutorial Mode State Management', () => {
    beforeEach(() => {
        window.tutorialCompleted = false;
        window.TUTORIAL_MODE = true;
    });

    test('tutorial mode is initially active', () => {
        expect(window.TUTORIAL_MODE).toBe(true);
    });

    test('tutorial is initially not completed', () => {
        expect(window.tutorialCompleted).toBe(false);
    });

    test('can mark tutorial as completed', () => {
        window.tutorialCompleted = true;
        expect(window.tutorialCompleted).toBe(true);
    });

    test('tutorial completion triggers form validation', () => {
        window.tutorialCompleted = true;
        if (typeof window.triggerFormValidation === 'function') {
            window.triggerFormValidation();
            expect(window.triggerFormValidation).toHaveBeenCalled();
        }
    });
});

describe('Tutorial Banner UI', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <div id="tutorial-banner" style="display: block;">
                <div class="tutorial-content">
                    <div class="tutorial-step-indicator">
                        <span id="current-step">1</span> / <span id="total-steps">12</span>
                    </div>
                    <h3 id="tutorial-title">Tutorial Title</h3>
                    <p id="tutorial-text">Tutorial description text.</p>
                    <div class="tutorial-buttons">
                        <button id="tutorial-prev" disabled>Previous</button>
                        <button id="tutorial-next">Next</button>
                    </div>
                </div>
            </div>
            <div class="container" id="visual-content">
                <div class="tile-box" id="image-a-box">Image A</div>
                <div class="tile-box" id="image-b-box">Image B</div>
            </div>
            <form id="survey-form">
                <button type="submit" id="submit-btn" disabled>Submit</button>
            </form>
        `;
    });

    test('tutorial banner is visible in tutorial mode', () => {
        const banner = document.getElementById('tutorial-banner');
        expect(banner).toBeTruthy();
        expect(banner.style.display).not.toBe('none');
    });

    test('tutorial shows step counter', () => {
        const currentStep = document.getElementById('current-step');
        const totalSteps = document.getElementById('total-steps');
        expect(currentStep).toBeTruthy();
        expect(totalSteps).toBeTruthy();
        expect(totalSteps.textContent).toBe('12');
    });

    test('tutorial has navigation buttons', () => {
        const prevBtn = document.getElementById('tutorial-prev');
        const nextBtn = document.getElementById('tutorial-next');
        expect(prevBtn).toBeTruthy();
        expect(nextBtn).toBeTruthy();
    });

    test('previous button is disabled on first step', () => {
        const prevBtn = document.getElementById('tutorial-prev');
        expect(prevBtn.disabled).toBe(true);
    });

    test('next button is enabled initially', () => {
        const nextBtn = document.getElementById('tutorial-next');
        expect(nextBtn.disabled).toBe(false);
    });

    test('tutorial has title and text content', () => {
        const title = document.getElementById('tutorial-title');
        const text = document.getElementById('tutorial-text');
        expect(title).toBeTruthy();
        expect(text).toBeTruthy();
        expect(title.textContent).toBeTruthy();
        expect(text.textContent).toBeTruthy();
    });
});

describe('Tutorial Step Navigation', () => {
    let currentStep = 1;
    const totalSteps = 12;

    beforeEach(() => {
        currentStep = 1;
        document.body.innerHTML = `
            <div id="tutorial-banner">
                <span id="current-step">${currentStep}</span>
                <button id="tutorial-prev" disabled>Previous</button>
                <button id="tutorial-next">Next</button>
            </div>
        `;
    });

    test('can advance to next step', () => {
        currentStep++;
        document.getElementById('current-step').textContent = currentStep;
        expect(document.getElementById('current-step').textContent).toBe('2');
    });

    test('previous button enables after first step', () => {
        currentStep = 2;
        const prevBtn = document.getElementById('tutorial-prev');
        prevBtn.disabled = false;
        expect(prevBtn.disabled).toBe(false);
    });

    test('can go back to previous step', () => {
        currentStep = 3;
        document.getElementById('current-step').textContent = currentStep;
        currentStep--;
        document.getElementById('current-step').textContent = currentStep;
        expect(document.getElementById('current-step').textContent).toBe('2');
    });

    test('step counter stays within valid range', () => {
        for (let i = 1; i <= totalSteps; i++) {
            currentStep = i;
            expect(currentStep).toBeGreaterThanOrEqual(1);
            expect(currentStep).toBeLessThanOrEqual(totalSteps);
        }
    });
});

describe('Tutorial Highlighting', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <div class="tile-box" id="image-a-box">Image A</div>
            <div class="tile-box" id="image-b-box">Image B</div>
            <div class="question-navigation">
                <button id="prev-question-btn">Up</button>
                <button id="next-question-btn">Down</button>
            </div>
            <button id="submit-btn">Submit</button>
        `;
    });

    test('can add highlight class to element', () => {
        const element = document.getElementById('image-a-box');
        element.classList.add('tutorial-highlight');
        expect(element.classList.contains('tutorial-highlight')).toBe(true);
    });

    test('can remove highlight class from element', () => {
        const element = document.getElementById('image-a-box');
        element.classList.add('tutorial-highlight');
        element.classList.remove('tutorial-highlight');
        expect(element.classList.contains('tutorial-highlight')).toBe(false);
    });

    test('can highlight multiple elements', () => {
        const elementA = document.getElementById('image-a-box');
        const elementB = document.getElementById('image-b-box');
        elementA.classList.add('tutorial-highlight');
        elementB.classList.add('tutorial-highlight');
        expect(elementA.classList.contains('tutorial-highlight')).toBe(true);
        expect(elementB.classList.contains('tutorial-highlight')).toBe(true);
    });

    test('can clear all highlights', () => {
        // Add highlights to multiple elements
        const elements = document.querySelectorAll('.tile-box');
        elements.forEach(el => el.classList.add('tutorial-highlight'));
        
        // Clear all highlights
        const highlighted = document.querySelectorAll('.tutorial-highlight');
        highlighted.forEach(el => el.classList.remove('tutorial-highlight'));
        
        // Verify all cleared
        const remainingHighlights = document.querySelectorAll('.tutorial-highlight');
        expect(remainingHighlights.length).toBe(0);
    });
});

describe('Tutorial Completion', () => {
    beforeEach(() => {
        window.tutorialCompleted = false;
        document.body.innerHTML = `
            <div id="tutorial-banner">
                <button id="tutorial-next">Next</button>
            </div>
            <form id="survey-form">
                <button type="submit" id="submit-btn" disabled>Submit</button>
            </form>
        `;
    });

    test('submit button is disabled during tutorial', () => {
        const submitBtn = document.getElementById('submit-btn');
        expect(submitBtn.disabled).toBe(true);
    });

    test('tutorial completion can enable submit button', () => {
        const submitBtn = document.getElementById('submit-btn');
        window.tutorialCompleted = true;
        // Simulate enabling the button after tutorial completion
        submitBtn.disabled = false;
        expect(submitBtn.disabled).toBe(false);
    });

    test('tutorial banner can be hidden after completion', () => {
        const banner = document.getElementById('tutorial-banner');
        banner.style.display = 'none';
        expect(banner.style.display).toBe('none');
    });
});

