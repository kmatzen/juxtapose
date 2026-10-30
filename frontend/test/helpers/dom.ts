import { afterEach } from 'vitest';

import type { Disposable } from '../../src/lib/dom';

// Mirrors index.html: a component test on a bespoke div passes on layouts the real page never ships.
export const SURVEY_HTML = `
<div id="tutorial-banner" style="display: none;">
  <div class="tutorial-content">
    <svg><path id="tutorial-progress-circle"></path><path id="tutorial-checkmark"></path></svg>
    <div class="tutorial-text"><h3 id="tutorial-title"></h3><p id="tutorial-text"></p></div>
    <div class="tutorial-buttons"><button class="btn-tutorial btn-tutorial-primary">Next</button></div>
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
    <ul class="info-box">
      <li><span id="user-browser">Detecting...</span></li>
      <li><span id="user-os">Detecting...</span></li>
      <li><span id="user-screen">Detecting...</span></li>
      <li><span id="user-pixel-ratio">Detecting...</span></li>
      <li><span id="user-color">Detecting...</span></li>
    </ul>
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
            ${radios('image_choice', ['A', 'B', 'equal'])}
            ${radios('image_confidence', ['1', '2', '3', '4', '5'])}
          </div>
          <div id="mask-evaluation" class="evaluation-section" data-depends-on="mask">
            ${radios('mask_choice', ['A', 'B', 'equal'])}
            ${radios('mask_confidence', ['1', '2', '3', '4', '5'])}
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

function radios(name: string, values: string[]): string {
    return values.map((v) => `<input type="radio" name="${name}" value="${v}">`).join('');
}

export function surveyFixture(): void {
    document.body.innerHTML = SURVEY_HTML;
}

const disposables: Disposable[] = [];

afterEach(() => {
    while (disposables.length) disposables.pop()?.dispose();
});

// Auto-disposed: a listener the component leaks fails the next test, which is the point.
// Auto-disposed: a listener the component leaks fails the next test, which is the point.
export function mount<P, R extends Disposable>(
    mountFn: (host: HTMLElement, props: P) => R,
    host: HTMLElement,
    props: P,
): R;
export function mount<R extends Disposable>(mountFn: (host: HTMLElement) => R, host: HTMLElement): R;
export function mount(
    mountFn: (host: HTMLElement, props?: unknown) => Disposable,
    host: HTMLElement,
    props?: unknown,
): Disposable {
    const mounted = mountFn(host, props);
    disposables.push(mounted);
    return mounted;
}

export function host(id: string): HTMLElement {
    const node = document.getElementById(id);
    if (!node) throw new Error(`no #${id} in the fixture`);
    return node;
}

export function answer(name: string, value: string): HTMLInputElement {
    const radio = document.querySelector<HTMLInputElement>(
        `#survey-form input[name="${name}"][value="${value}"]`,
    );
    if (!radio) throw new Error(`no radio ${name}=${value}`);
    radio.checked = true;
    radio.dispatchEvent(new Event('change', { bubbles: true }));
    return radio;
}

export function submit(formId: string): Event {
    const form = document.getElementById(formId);
    if (!form) throw new Error(`no #${formId}`);
    const event = new Event('submit', { bubbles: true, cancelable: true });
    form.dispatchEvent(event);
    return event;
}

export function byText(root: ParentNode, text: string): HTMLElement {
    const nodes = Array.from(root.querySelectorAll<HTMLElement>('button, a, p, span, h1, h2, h3, label, li, strong'));
    const found = nodes.find((n) => n.textContent?.trim() === text);
    if (!found) throw new Error(`no element reading ${JSON.stringify(text)}`);
    return found;
}

// Image decode callbacks land on microtasks; timers (auto-advance, banner auto-hide) need real time.
export function flush(): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, 0));
}

export function stubLocation(start = '/survey'): { href: string } {
    const location = { href: start };
    Object.defineProperty(window, 'location', { configurable: true, writable: true, value: location });
    return location;
}

export function stubScrolling(): void {
    window.scrollTo = () => {};
    (window.Element.prototype as Element & { scrollTo?: unknown }).scrollTo = () => {};
    (window.Element.prototype as Element & { scrollIntoView?: unknown }).scrollIntoView = () => {};
}
