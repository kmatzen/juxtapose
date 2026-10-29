const { script, surveyDom } = require('./helpers/survey-env');

const modal = () => document.getElementById('retake-modal');
const locked = () => document.documentElement.classList.contains('modal-open');

describe('retake modal', () => {
    beforeEach(() => {
        surveyDom();
        document.documentElement.classList.remove('modal-open');
    });

    it('locks the page while the participant is deciding', () => {
        script.showRetakeModal();
        expect(modal().classList.contains('show')).toBe(true);
        expect(locked()).toBe(true);
    });

    it('restores the page on cancel', async () => {
        const deciding = script.showRetakeModal();
        document.getElementById('retake-cancel').click();
        expect(await deciding).toBe(false);
        expect(locked()).toBe(false);
    });

    it('restores the page on confirm', async () => {
        const deciding = script.showRetakeModal();
        document.getElementById('retake-confirm').click();
        expect(await deciding).toBe(true);
        expect(locked()).toBe(false);
    });

    it('restores the scroll position the participant was at', async () => {
        Object.defineProperty(window, 'scrollY', { value: 300, configurable: true });
        const scrolls = [];
        window.scrollTo = (x, y) => scrolls.push([x, y]);

        const deciding = script.showRetakeModal();
        expect(document.documentElement.style.getPropertyValue('--modal-scroll-y')).toBe('300px');
        document.getElementById('retake-cancel').click();
        await deciding;
        await new Promise(resolve => requestAnimationFrame(resolve));

        expect(scrolls.at(-1)).toEqual([0, 300]);  // earlier tests' restores land in this frame
    });

    it('restores the page when the backdrop is clicked', async () => {
        const deciding = script.showRetakeModal();
        modal().click();
        expect(await deciding).toBe(false);
        expect(locked()).toBe(false);
    });
});
