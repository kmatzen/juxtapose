const {
    CONFIG,
    PAIR,
    answer,
    apiMock,
    flush,
    seam,
    loadSurvey,
    script,
    stubLocation,
    stubScrolling,
    submit,
    surveyDom,
} = require('./helpers/survey-env');

const postBody = (url) => {
    const calls = global.fetch.mock.calls.filter(([u, opts]) => u === url && opts && opts.body);
    return calls.length ? JSON.parse(calls[calls.length - 1][1].body) : undefined;
};
const postCount = (url) => global.fetch.mock.calls.filter(([u]) => u === url).length;

async function answeredSurvey(answers = [
    ['image_choice', 'A'], ['image_confidence', '4'],
    ['mask_choice', 'B'], ['mask_confidence', '3'],
]) {
    global.fetch = apiMock({
        '/api/get_image_pair': PAIR,
        '/api/submit_survey': { success: true, completed: false },
    });
    script.setupEventListeners();
    await script.loadImagePair(0);
    await flush();
    answers.forEach(([name, value]) => answer(name, value));
}

let location;

beforeEach(async () => {
    surveyDom();
    stubScrolling();
    location = stubLocation();
    await loadSurvey();
});

describe('survey submission payload', () => {
    beforeEach(() => { document.head.innerHTML = '<meta name="csrf-token" content="tok-1">'; });

    test('posts one structured response per answered question', async () => {
        await answeredSurvey();

        submit('survey-form');
        await flush();

        expect(postBody('/api/submit_survey').responses).toEqual({
            image: { choice: 'A', confidence: 4 },
            mask: { choice: 'B', confidence: 3 },
        });
    });

    test('leaves out a question whose section is hidden', async () => {
        await answeredSurvey();
        // The component's contract with script.js is a hidden section; the visibility rule itself
        // is study-state.isSectionVisible, covered on the vitest side.
        document.getElementById('mask-evaluation').style.display = 'none';

        submit('survey-form');
        await flush();

        expect(postBody('/api/submit_survey').responses).toEqual({
            image: { choice: 'A', confidence: 4 },
        });
    });

    test('carries the pair it was answering, including the randomisation flag', async () => {
        await answeredSurvey();

        submit('survey-form');
        await flush();

        const body = postBody('/api/submit_survey');
        expect(body.image_pair_id).toBe(PAIR.id);
        expect(body.was_randomized).toBe(true);
        expect(body.stimulus_data).toMatchObject({
            prompt: PAIR.prompt,
            method_a: PAIR.method_a,
            method_b: PAIR.method_b,
            image_a_url: PAIR.image_a_url,
            image_b_url: PAIR.image_b_url,
            identity_urls: PAIR.identity_urls,
            mask_url: PAIR.mask_url,
        });
    });

    test('reports time spent in seconds once the images were shown', async () => {
        await answeredSurvey();
        const before = Date.now();

        submit('survey-form');
        await flush();

        const { time_spent: timeSpent } = postBody('/api/submit_survey');
        expect(typeof timeSpent).toBe('number');
        expect(Number.isInteger(timeSpent)).toBe(false);
        expect(timeSpent).toBeLessThan((Date.now() - before) / 1000 + 1);
    });

    test('posts likert, free text and multiple choice in the shapes the server flattens', async () => {
        const config = {
            ...CONFIG,
            questions: [
                { name: 'quality', label: 'Quality', type: 'likert', required: true },
                { name: 'notes', label: 'Notes', type: 'free_text', required: false },
                {
                    name: 'usage', label: 'Usage', type: 'multiple_choice', required: true,
                    options: [{ value: 'pro', label: 'Professional' }],
                },
            ],
        };
        await loadSurvey(config);
        document.querySelector('.questions-container').innerHTML = `
            <div id="quality-evaluation" class="evaluation-section">
                <input type="radio" name="quality_value" value="2">
            </div>
            <div id="notes-evaluation" class="evaluation-section">
                <textarea name="notes_text">crisper edges</textarea>
            </div>
            <div id="usage-evaluation" class="evaluation-section">
                <input type="radio" name="usage_value" value="pro">
            </div>
        `;
        await answeredSurvey([['quality_value', '2'], ['usage_value', 'pro']]);

        submit('survey-form');
        await flush();

        expect(postBody('/api/submit_survey').responses).toEqual({
            quality: { value: 2 },
            notes: { text: 'crisper edges' },
            usage: { value: 'pro' },
        });
    });

    test('sends the page CSRF token as a header', async () => {
        await answeredSurvey();

        submit('survey-form');
        await flush();

        const call = global.fetch.mock.calls.find(([u, opts]) => u === '/api/submit_survey' && opts);
        expect(call[1]).toMatchObject({
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': 'tok-1' },
        });
    });

    test('loads the next pair after a successful submit', async () => {
        await answeredSurvey();

        submit('survey-form');
        await flush();

        expect(global.fetch).toHaveBeenCalledWith('/api/get_image_pair/1');
        expect(location.href).toBe('/survey');
    });

    test('redirects home when the study is finished', async () => {
        await answeredSurvey();
        global.fetch = apiMock({ '/api/submit_survey': { success: true, completed: true } });

        submit('survey-form');
        await flush();

        expect(location.href).toBe('/');
    });

    test('keeps the answers and shows an error when the server rejects', async () => {
        await answeredSurvey();
        global.fetch = apiMock({
            '/api/get_image_pair': PAIR,
            '/api/submit_survey': { ok: false, status: 400, json: { success: false, error: 'bad' } },
        });

        submit('survey-form');
        await flush();

        expect(seam().shown).toContain('Failed to submit response. Please try again.');
        expect(document.querySelector('input[name="image_choice"]:checked').value).toBe('A');
    });

    test('a tutorial submit completes the tutorial and never posts a response', async () => {
        seam().setTutorial();
        global.fetch = apiMock({ '/api/complete_tutorial': { success: true } });
        script.setupEventListeners();

        submit('survey-form');
        await flush();

        expect(postCount('/api/submit_survey')).toBe(0);
        expect(postCount('/api/complete_tutorial')).toBe(1);
        expect(location.href).toBe('/');
    });
});
