// Harness for suites driving the real script.js; the DOM mirrors src/survey/templates/index.html.
const path = require('path');

const script = require(path.join(__dirname, '../../../src/survey/static/script.js'));

const CONFIG = {
    dev_mode: false,
    survey: { title: 'Image Comparison' },
    inputs: [
        { name: 'mask', type: 'image', column: 'mask_url', label: 'Spatial Mask' },
        { name: 'identity', type: 'image_gallery', column: 'identity_urls', label: 'Reference' },
    ],
    outputs: [{ name: 'image', type: 'image', column_a: 'image_a_url', column_b: 'image_b_url' }],
    questions: [
        { name: 'image', label: 'Which image is better?', type: 'ab_preference', confidence: true, required: true, section_label: 'Image quality' },
        { name: 'mask', label: 'Which mask matches?', type: 'ab_preference', confidence: true, required: true, depends_on: 'mask', section_label: 'Mask' },
    ],
    demographics: [
        { name: 'email', type: 'email', label: 'Email', required: true },
        { name: 'occupation', type: 'text', label: 'Occupation' },
        { name: 'tools', type: 'checkbox', label: 'Tools used' },
    ],
    tutorial: { steps: [{ title: 'Images', text: 'Compare A and B', highlight: '.tile-image' }, 'auto_questions'] },
};

const PAIR = {
    id: 7,
    prompt: 'a red cube',
    method_a: 'MethodA',
    method_b: 'MethodB',
    image_a_url: 'https://img/a.png',
    image_b_url: 'https://img/b.png',
    identity_urls: 'https://img/id1.png,https://img/id2.png',
    mask_url: 'https://img/mask.png',
    was_randomized: true,
    total_pairs: 3,
};

const radioGroup = (name, values) =>
    values.map(v => `<input type="radio" name="${name}" value="${v}">`).join('\n');

function surveyDom() {
    document.body.innerHTML = `
        <div id="tutorial-banner" style="display: none;">
            <div class="tutorial-content">
                <svg><path id="tutorial-progress-circle"></path><path id="tutorial-checkmark"></path></svg>
                <div class="tutorial-text">
                    <h3 id="tutorial-title"></h3>
                    <p id="tutorial-text"></p>
                </div>
                <div class="tutorial-buttons">
                    <button class="btn-tutorial btn-tutorial-primary" onclick="nextTutorialStep()">Next</button>
                </div>
            </div>
        </div>
        <div class="container">
            <div class="progress-container">
                <div id="survey-progress" class="survey-progress" style="display: none;">
                    <span id="current-question">1</span>/<span id="total-questions">3</span>
                    <div class="progress-bar"><div id="progress-bar-fill"></div></div>
                </div>
            </div>
            <section id="demographics-section" class="section active">
                <form id="demographics-form">
                    <input type="email" id="email" name="email" value="a@b.c">
                    <input type="text" id="occupation" name="occupation" value="Designer">
                    <input type="checkbox" id="tools-dalle" name="tools[]" value="dalle" checked>
                    <input type="checkbox" id="tools-sd" name="tools[]" value="sd" checked>
                    <select id="ai_usage" name="ai_usage"><option value="often" selected>Often</option></select>
                    <button type="submit" id="submit-demographics-btn">Continue</button>
                </form>
            </section>
            <section id="survey-section" class="section">
                <p class="instruction"><span id="total-pairs-text">multiple pairs</span></p>
                <form id="survey-form">
                    <div class="visual-content-section">
                        <div class="prompt-box"><p id="prompt-text">Loading...</p></div>
                        <div id="identity-section" class="conditioning-box">
                            <div id="identity-images" class="identity-images-container"></div>
                        </div>
                        <div class="three-tile-grid">
                            <div class="tile-box mask-tile"><div class="tile-image-container">
                                <img id="mask-image" class="tile-image" src="" alt="Spatial Mask">
                            </div></div>
                            <div class="tile-box"><div class="tile-image-container">
                                <img id="image-a" class="tile-image" src="" alt="Image A">
                            </div></div>
                            <div class="tile-box"><div class="tile-image-container">
                                <img id="image-b" class="tile-image" src="" alt="Image B">
                            </div></div>
                        </div>
                    </div>
                    <div class="questions-section">
                        <div class="questions-container">
                            <div id="image-evaluation" class="evaluation-section">
                                ${radioGroup('image_choice', ['A', 'B', 'equal'])}
                                ${radioGroup('image_confidence', ['1', '2', '3', '4', '5'])}
                            </div>
                            <div id="mask-evaluation" class="evaluation-section" data-depends-on="mask">
                                ${radioGroup('mask_choice', ['A', 'B', 'equal'])}
                                ${radioGroup('mask_confidence', ['1', '2', '3', '4', '5'])}
                            </div>
                        </div>
                        <div class="question-navigation">
                            <button type="button" class="btn" id="prev-question-btn" disabled>&uarr;</button>
                            <button type="button" class="btn" id="next-question-btn">&darr;</button>
                        </div>
                        <button type="submit" class="btn btn-primary" id="submit-btn" disabled>&rarr;</button>
                    </div>
                </form>
            </section>
        </div>
        <div id="retake-modal" class="modal" style="display:none;">
            <button id="retake-cancel">Cancel</button>
            <button id="retake-confirm">Continue and Retake</button>
        </div>
        <div id="image-lightbox" class="lightbox">
            <button class="lightbox-close">&times;</button>
            <div class="lightbox-content">
                <img id="lightbox-image" src="" alt="Large view">
                <div class="lightbox-caption"></div>
            </div>
        </div>
    `;
}

function apiMock(routes) {
    return jest.fn((url, options) => {
        const key = Object.keys(routes).find(k => url === k || url.startsWith(k));
        if (!key) throw new Error(`unmocked fetch: ${url}`);
        const reply = typeof routes[key] === 'function' ? routes[key](options) : routes[key];
        const { ok = true, status = 200, json, ...payload } = reply;
        return Promise.resolve({ ok, status, json: () => Promise.resolve(json === undefined ? payload : json) });
    });
}

function autoLoadingImages({ manual = false } = {}) {
    const requested = [];
    const failing = [];
    const pending = [];
    const fire = (img) => {
        if (failing.some(match => String(img._src).includes(match))) {
            if (img.onerror) img.onerror(new Error(`blocked ${img._src}`));
        } else if (img.onload) {
            img.onload();
        }
    };
    global.Image = class Image {
        constructor() {
            this.onload = null;
            this.onerror = null;
            this.width = 100;
            this.height = 100;
            this._src = '';
        }
        set src(value) {
            this._src = value;
            requested.push(value);
            // Manual mode lets a test observe the state between the request and the decode.
            if (manual) {
                pending.push(this);
                return;
            }
            Promise.resolve().then(() => fire(this));
        }
        get src() { return this._src; }
    };
    return {
        requested,
        fail: (...substrings) => failing.push(...substrings),
        loadAll: () => pending.splice(0).forEach(fire),
    };
}

function stubLocation(start = '/survey') {
    const location = { href: start };
    Object.defineProperty(window, 'location', {
        configurable: true,
        writable: true,
        value: location,
    });
    return location;
}

function stubScrolling() {
    window.scrollTo = jest.fn();
    window.pageYOffset = 0;
    // jsdom implements neither, and script.js calls both; fresh mocks keep call counts per test.
    window.Element.prototype.scrollTo = jest.fn();
    window.Element.prototype.scrollIntoView = jest.fn();
    return window.Element.prototype.scrollTo;
}

// The components in frontend/src/components are collaborators of script.js now: the suite stubs
// the seam and asserts the page asked for the thing; the components' own tests cover the rendering.
function installSeam() {
    const seam = {
        shown: [],
        asks: 0,
        answer: null,
        opened: [],
        banner: { show: (message) => seam.shown.push(message), hide() {}, dispose() {} },
        lightbox: { open: (src, caption) => seam.opened.push([src, caption]), close() {}, dispose() {} },
        // Held open on purpose: a test must see that nothing destructive posted before the answer.
        retake: {
            ask: () => {
                seam.asks += 1;
                return new Promise((resolve) => {
                    seam.answer = resolve;
                });
            },
            dispose() {},
        },
    };
    window.__JX__ = seam;
    return seam;
}

function seam() {
    if (!window.__JX__) throw new Error('no seam: call loadSurvey() or installSeam() first');
    return window.__JX__;
}

function loadSurvey(config = CONFIG) {
    surveyDom();
    autoLoadingImages();
    installSeam();
    global.fetch = apiMock({ '/api/config': config });
    return script.checkDevMode();
}

function answer(name, value) {
    const radio = document.querySelector(`#survey-form input[name="${name}"][value="${value}"]`);
    if (!radio) throw new Error(`no radio ${name}=${value}`);
    radio.checked = true;
    radio.dispatchEvent(new Event('change', { bubbles: true }));
    return radio;
}

function submit(formId) {
    const form = document.getElementById(formId);
    const event = new Event('submit', { bubbles: true, cancelable: true });
    form.dispatchEvent(event);
    return event;
}

// Image load callbacks land on microtasks; timers (auto-advance) need real time.
const flush = () => new Promise(resolve => setTimeout(resolve, 0));

module.exports = {
    CONFIG,
    installSeam,
    seam,
    PAIR,
    answer,
    apiMock,
    autoLoadingImages,
    flush,
    loadSurvey,
    script,
    stubLocation,
    stubScrolling,
    submit,
    surveyDom,
};
