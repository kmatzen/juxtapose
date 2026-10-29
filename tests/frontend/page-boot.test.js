const {
    PAIR,
    apiMock,
    flush,
    loadSurvey,
    script,
    stubScrolling,
    surveyDom,
} = require('./helpers/survey-env');

beforeEach(async () => {
    surveyDom();
    stubScrolling();
    await loadSurvey();
});

describe('checkDemographicsSubmitted', () => {
    test('a returning participant skips straight to the first pair', async () => {
        global.fetch = apiMock({
            '/api/check_demographics': { submitted: true },
            '/api/get_image_pair': PAIR,
        });

        await script.checkDemographicsSubmitted();
        await flush();

        expect(document.getElementById('demographics-section').classList.contains('active')).toBe(false);
        expect(document.getElementById('survey-section').classList.contains('active')).toBe(true);
        expect(document.getElementById('survey-progress').style.display).toBe('block');
        expect(global.fetch).toHaveBeenCalledWith('/api/get_image_pair/0');
        expect(document.getElementById('image-a').src).toBe(PAIR.image_a_url);
    });

    test('a first-time participant stays on the demographics form', async () => {
        global.fetch = apiMock({ '/api/check_demographics': { submitted: false } });

        await script.checkDemographicsSubmitted();
        await flush();

        expect(document.getElementById('survey-section').classList.contains('active')).toBe(false);
        expect(global.fetch).not.toHaveBeenCalledWith('/api/get_image_pair/0');
    });

    test('a failed check leaves the page on demographics rather than blanking it', async () => {
        global.fetch = jest.fn(() => Promise.reject(new Error('offline')));

        await script.checkDemographicsSubmitted();
        await flush();

        expect(document.getElementById('demographics-section').classList.contains('active')).toBe(true);
    });
});

describe('image lightbox', () => {
    const lightbox = () => document.getElementById('image-lightbox');

    beforeEach(() => script.setupEventListeners());

    test('opening shows the full image with a caption', () => {
        window.openLightbox('https://img/a.png', 'Image A');

        expect(document.getElementById('lightbox-image').src).toBe('https://img/a.png');
        expect(document.querySelector('.lightbox-caption').textContent).toBe('Image A');
        expect(lightbox().classList.contains('show')).toBe(true);
    });

    test('escape, the close button and the backdrop all dismiss it', () => {
        window.openLightbox('https://img/a.png', 'Image A');

        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        expect(lightbox().classList.contains('show')).toBe(false);

        window.openLightbox('https://img/b.png', 'Image B');
        document.querySelector('.lightbox-close').click();
        expect(lightbox().classList.contains('show')).toBe(false);

        window.openLightbox('https://img/b.png', 'Image B');
        lightbox().dispatchEvent(new Event('click'));
        expect(lightbox().classList.contains('show')).toBe(false);
    });

    test('escape is ignored while the lightbox is closed', () => {
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        expect(lightbox().classList.contains('show')).toBe(false);
    });
});
