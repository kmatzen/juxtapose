const {
    answer,
    loadSurvey,
    script,
    stubScrolling,
    surveyDom,
} = require('./helpers/survey-env');

const sections = () => Array.from(document.querySelectorAll('.questions-container .evaluation-section'));
const prevBtn = () => document.getElementById('prev-question-btn');
const nextBtn = () => document.getElementById('next-question-btn');
const containerScroll = () => document.querySelector('.questions-container').scrollTo;

let observers;

beforeEach(async () => {
    surveyDom();
    stubScrolling();
    observers = [];
    // Captured so a test can deliver the intersection entries jsdom will never produce.
    window.IntersectionObserver = class {
        constructor(callback) {
            this.callback = callback;
            observers.push(this);
        }
        observe() {}
        unobserve() {}
        disconnect() {}
    };
    await loadSurvey();
});

describe('initializeProgressiveQuestions', () => {
    test('shows every section and starts on the first', () => {
        script.initializeProgressiveQuestions();
        expect(sections().every(s => s.classList.contains('active'))).toBe(true);
        expect(prevBtn().disabled).toBe(true);
        expect(nextBtn().disabled).toBe(false);
    });

    test('sizes the questions box to one and a half questions', () => {
        const box = document.querySelector('.questions-section');
        box.style.maxHeight = '9999px';
        Object.defineProperty(sections()[0], 'offsetHeight', { value: 200, configurable: true });

        script.initializeProgressiveQuestions();

        expect(box.style.height).toBe('auto');
        expect(box.style.maxHeight).toBe('300px');
    });

    test('is a no-op on a page without question sections', () => {
        document.querySelector('.questions-container').remove();
        expect(() => script.initializeProgressiveQuestions()).not.toThrow();
    });

    test('the nav buttons move between sections', () => {
        script.initializeProgressiveQuestions();

        nextBtn().click();
        expect(prevBtn().disabled).toBe(false);
        expect(containerScroll()).toHaveBeenCalledTimes(1);

        prevBtn().click();
        expect(prevBtn().disabled).toBe(true);
        expect(containerScroll()).toHaveBeenCalledTimes(2);
    });
});

describe('navigateQuestion', () => {
    test('walks to the last section and stops', () => {
        script.initializeProgressiveQuestions();

        script.navigateQuestion(1);
        expect(nextBtn().disabled).toBe(true);

        script.navigateQuestion(1);
        expect(nextBtn().disabled).toBe(true);
        expect(containerScroll()).toHaveBeenCalledTimes(1);
    });

    test('will not go before the first section', () => {
        script.initializeProgressiveQuestions();

        script.navigateQuestion(-1);

        expect(containerScroll()).not.toHaveBeenCalled();
        expect(prevBtn().disabled).toBe(true);
    });
});

describe('isQuestionGroupComplete', () => {
    test('a section needs an answer in every radio group it contains', () => {
        script.initializeProgressiveQuestions();

        answer('image_choice', 'A');
        expect(script.isQuestionGroupComplete(0)).toBe(false);

        answer('image_confidence', '3');
        expect(script.isQuestionGroupComplete(0)).toBe(true);
    });

    test('the other section’s answers do not count towards it', () => {
        script.initializeProgressiveQuestions();

        answer('mask_choice', 'A');
        answer('mask_confidence', '3');
        expect(script.isQuestionGroupComplete(0)).toBe(false);
        expect(script.isQuestionGroupComplete(1)).toBe(true);
    });
});

describe('auto-advance', () => {
    beforeEach(() => jest.useFakeTimers());
    afterEach(() => jest.useRealTimers());

    test('the section turns the page once its last answer is picked', () => {
        script.initializeProgressiveQuestions();
        answer('image_choice', 'A');

        answer('image_confidence', '3');
        jest.advanceTimersByTime(500);

        expect(containerScroll()).toHaveBeenCalledTimes(1);
        expect(prevBtn().disabled).toBe(false);
    });

    test('an incomplete section does not move the page', () => {
        script.initializeProgressiveQuestions();

        answer('image_choice', 'A');
        jest.advanceTimersByTime(500);

        expect(containerScroll()).not.toHaveBeenCalled();
        expect(prevBtn().disabled).toBe(true);
    });

    test('completing the last section reveals submit', () => {
        script.initializeProgressiveQuestions();
        script.navigateQuestion(1);
        const submitScroll = document.getElementById('submit-btn').scrollIntoView;
        submitScroll.mockClear();

        answer('mask_choice', 'A');
        answer('mask_confidence', '3');
        jest.advanceTimersByTime(500);

        expect(submitScroll).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' });
    });
});

describe('scroll tracking', () => {
    test('scrolling a section into view moves the nav state to it', () => {
        script.initializeProgressiveQuestions();
        expect(prevBtn().disabled).toBe(true);

        observers[0].callback([
            { target: sections()[1], isIntersecting: true, intersectionRatio: 1 },
        ]);

        expect(prevBtn().disabled).toBe(false);
        expect(nextBtn().disabled).toBe(true);
    });

    test('barely visible and off-screen sections are ignored', () => {
        script.initializeProgressiveQuestions();

        observers[0].callback([
            { target: sections()[1], isIntersecting: true, intersectionRatio: 0.1 },
            { target: sections()[1], isIntersecting: false, intersectionRatio: 1 },
        ]);

        expect(prevBtn().disabled).toBe(true);
    });

    test('the observer watches the questions container', () => {
        script.initializeProgressiveQuestions();

        expect(observers).toHaveLength(1);
        expect(observers[0].callback).toEqual(expect.any(Function));
    });
});
