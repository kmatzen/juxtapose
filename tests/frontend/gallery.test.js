// Audit #15: image_gallery is documented as "comma-separated URLs or a single stacked image".
const path = require('path');

const SCRIPT_PATH = path.join(__dirname, '../../src/survey/static/script.js');
global.window = global;
const script = require(SCRIPT_PATH);

const CONFIG = {
    dev_mode: false,
    inputs: [{ name: 'identity', type: 'image_gallery', column: 'identity_urls', label: 'Reference' }],
    outputs: [{ name: 'image', type: 'image', column_a: 'a', column_b: 'b' }],
    questions: []
};

function stackedImageSpy() {
    const requested = [];
    global.Image = function Image() {
        let src = '';
        Object.defineProperty(this, 'src', {
            set: (v) => { src = v; requested.push(v); },
            get: () => src,
        });
    };
    return requested;
}

describe('image_gallery renders the documented formats (audit #15)', () => {
    let requested;

    beforeEach(async () => {
        document.body.innerHTML = `
            <div id="identity-section">
                <div id="identity-images"></div>
            </div>
            <img id="image-a"><img id="image-b">
        `;
        global.fetch = jest.fn(() =>
            Promise.resolve({ ok: true, json: () => Promise.resolve(CONFIG) })
        );
        await script.checkDevMode();
        requested = stackedImageSpy();
    });

    test('comma-separated urls render one img each', () => {
        script.displayConditioningInputs({
            identity_urls: 'https://x/1.jpg, https://x/2.jpg ,https://x/3.jpg'
        });

        const imgs = Array.from(document.querySelectorAll('#identity-images img'));
        expect(imgs.map(i => i.src)).toEqual([
            'https://x/1.jpg', 'https://x/2.jpg', 'https://x/3.jpg'
        ]);
        expect(imgs.every(i => i.classList.contains('identity-image'))).toBe(true);
    });

    test('a single stacked url keeps the stacked-slice path', () => {
        script.displayConditioningInputs({ identity_urls: 'https://x/stacked.jpg' });

        expect(requested).toEqual(['https://x/stacked.jpg']);
        expect(document.querySelectorAll('#identity-images img')).toHaveLength(0);
    });
});
