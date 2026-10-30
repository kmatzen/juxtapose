const { PAIR, apiMock, flush, loadSurvey, script, stubScrolling, surveyDom } =
    require('./helpers/survey-env');

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
