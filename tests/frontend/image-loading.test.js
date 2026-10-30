const {
    PAIR,
    answer,
    apiMock,
    autoLoadingImages,
    flush,
    loadSurvey,
    seam,
    script,
    stubLocation,
    stubScrolling,
    surveyDom,
} = require('./helpers/survey-env');

const el = (id) => document.getElementById(id);
const form = () => el('survey-form');
const srcOf = (id) => el(id).getAttribute('src');

async function loadPair(overrides = {}, index = 0) {
    global.fetch = apiMock({ '/api/get_image_pair': { ...PAIR, ...overrides } });
    await script.loadImagePair(index);
    await flush();
}

beforeEach(async () => {
    surveyDom();
    stubScrolling();
    await loadSurvey();
});

describe('loadImagePair renders a pair', () => {
    test('requests the pair by index', async () => {
        await loadPair();
        expect(global.fetch).toHaveBeenCalledWith('/api/get_image_pair/0');
    });

    test('shows prompt, images and method metadata after the images decode', async () => {
        await loadPair();
        expect(el('prompt-text').textContent).toBe(PAIR.prompt);
        expect(el('image-a').src).toBe(PAIR.image_a_url);
        expect(el('image-b').src).toBe(PAIR.image_b_url);
        expect(el('image-a').dataset.method).toBe(PAIR.method_a);
        expect(el('image-b').dataset.method).toBe(PAIR.method_b);
        expect(el('image-a').style.opacity).toBe('1');
        expect(el('image-b').style.opacity).toBe('1');
        expect(el('total-pairs-text').textContent).toBe('You will see 3 image pairs in total.');
    });

    test('updates the pair counters and progress bar', async () => {
        await loadPair({}, 1);
        expect(el('current-question').textContent).toBe('2');
        expect(el('total-questions').textContent).toBe(String(PAIR.total_pairs));
        expect(el('progress-bar-fill').style.width).toBe(`${(1 / 3) * 100}%`);
    });

    test('a resumed pair counts from the server position, not the reloaded index', async () => {
        await loadPair({ trials_remaining: 2 }, 0);

        expect(el('current-question').textContent).toBe('2');
        expect(el('total-questions').textContent).toBe(String(PAIR.total_pairs));
        expect(el('progress-bar-fill').style.width).toBe(`${(1 / 3) * 100}%`);
    });

    test('writes the singular wording for a single-pair study', async () => {
        await loadPair({ total_pairs: 1 });
        expect(el('total-pairs-text').textContent).toBe('You will see 1 image pair in total.');
    });

    test('renders the identity gallery from the pair data', async () => {
        await loadPair();
        const srcs = Array.from(document.querySelectorAll('#identity-images img')).map(i => i.src);
        expect(srcs).toEqual([PAIR.identity_urls.split(',')[0], PAIR.identity_urls.split(',')[1]]);
    });

    test('hides the dependent mask question when the pair has no mask', async () => {
        await loadPair({ mask_url: '' });
        expect(el('mask-evaluation').style.display).toBe('none');
    });
});

describe('the form is locked while images are in flight', () => {
    let resolveFetch;

    beforeEach(() => {
        global.fetch = jest.fn(() => new Promise(resolve => { resolveFetch = resolve; }));
    });

    test('inputs stay inert until both images decode, then re-enable', async () => {
        const images = autoLoadingImages({ manual: true });
        global.fetch = jest.fn(() => new Promise(resolve => { resolveFetch = resolve; }));

        const pending = script.loadImagePair(0);
        resolveFetch({ ok: true, json: () => Promise.resolve(PAIR) });
        await flush();

        expect(form().style.pointerEvents).toBe('none');
        expect(document.querySelectorAll('.loading-indicator')).toHaveLength(2);
        expect(srcOf('image-a')).toBe('');

        images.loadAll();
        await flush();

        expect(document.querySelectorAll('.loading-indicator')).toHaveLength(0);
        expect(el('image-a').src).toBe(PAIR.image_a_url);
        expect(form().style.pointerEvents).toBe('auto');
        expect(form().style.opacity).toBe('1');
        await pending;
    });

    test('a failed image shows an error and unlocks the form', async () => {
        const images = autoLoadingImages();
        images.fail('b.png');
        global.fetch = apiMock({ '/api/get_image_pair': PAIR });

        await script.loadImagePair(0);
        await flush();

        expect(seam().shown.join(' ')).toContain('Image B');
        expect(form().style.pointerEvents).toBe('auto');
        expect(srcOf('image-a')).toBe('');
    });
});

describe('loadImagePair failure paths', () => {
    let error;

    beforeEach(() => {
        error = jest.spyOn(console, 'error').mockImplementation(() => {});
    });

    afterEach(() => error.mockRestore());

    test('a non-ok response surfaces an error and renders no images', async () => {
        global.fetch = apiMock({ '/api/get_image_pair': { ok: false, status: 500, json: { error: 'boom' } } });

        await script.loadImagePair(0);
        await flush();

        expect(seam().shown).toContain('Failed to load image pair. Please refresh the page.');
        expect(srcOf('image-a')).toBe('');
        expect(error).toHaveBeenCalled();
    });

    test('a network failure surfaces an error', async () => {
        global.fetch = jest.fn(() => Promise.reject(new Error('offline')));

        await script.loadImagePair(0);
        await flush();

        expect(seam().shown).toContain('Network error. Please check your connection.');
    });

    test('a 404 means nothing is owed, so it hands over to the index route', async () => {
        const location = stubLocation('/survey');
        global.fetch = apiMock({ '/api/get_image_pair': { ok: false, status: 404, json: { error: 'Invalid image pair index' } } });

        await script.loadImagePair(0);
        await flush();

        expect(location.href).toBe('/');
        expect(seam().shown).toEqual([]);
    });

    test('a second pair clears the previous pair overlays and answers', async () => {
        await loadPair({ id: 1 });
        answer('image_choice', 'A');
        const stale = document.createElement('div');
        stale.className = 'mask-overlay';
        document.body.appendChild(stale);

        await loadPair({ id: 2 }, 1);

        expect(document.querySelectorAll('.mask-overlay')).toHaveLength(0);
        expect(document.querySelector('input[name="image_choice"]:checked')).toBeNull();
    });
});

describe('a trial with empty optional columns clears the previous trial tiles', () => {
    test('identity and mask tiles go away instead of showing trial N-1', async () => {
        await loadPair();
        expect(el('identity-section').style.display).toBe('block');
        expect(document.querySelectorAll('#identity-images .identity-image')).toHaveLength(2);

        await loadPair({ id: 8, mask_url: '', identity_urls: '' }, 1);

        expect(el('identity-section').style.display).toBe('none');
        expect(document.querySelectorAll('#identity-images .identity-image')).toHaveLength(0);
        expect(el('mask-image').hasAttribute('src')).toBe(false);
        expect(document.querySelector('.mask-tile').style.display).toBe('none');
    });

    test('tiles stay on screen when the columns carry values', async () => {
        await loadPair();

        expect(el('identity-section').style.display).toBe('block');
        expect(el('mask-image').getAttribute('src')).toBe(PAIR.mask_url);
        expect(document.querySelector('.mask-tile').style.display).toBe('');
    });
});
