import { escapeHtml, qa } from '../lib/dom';
import type { Disposable } from '../lib/dom';
import type { TutorialStep } from '../study-state';

export type TutorialBannerProps = {
    /** Read at start(): the walkthrough cannot be built before the study config arrives. */
    steps: () => TutorialStep[];
    /** Fires once at the end: the walkthrough is what gates Submit, so finishing is a validation event. */
    onComplete: () => void;
};

export type TutorialBanner = Disposable & {
    start(): void;
    /** Also true when the study has no tutorial, so callers never have to special-case its absence. */
    isComplete(): boolean;
    next(): void;
};

const HIGHLIGHT = 'tutorial-highlight';

/** Tutorial walkthrough. Its highlighting is the one intentional page-scoped query: pointing at markup it does not own is the job. */
export function createTutorialBanner(banner: HTMLElement, props: TutorialBannerProps): TutorialBanner {
    const title = requireWithin(banner, '#tutorial-title');
    const text = requireWithin(banner, '#tutorial-text');
    const circle = requireWithin(banner, '#tutorial-progress-circle');
    const checkmark = requireWithin(banner, '#tutorial-checkmark');
    const nextButton = requireWithin(banner, '.btn-tutorial-primary');

    let steps: TutorialStep[] = [];
    let index = 0;
    let started = false;
    let complete = false;

    function clearHighlights(): void {
        for (const el of qa<HTMLElement>(document, `.${HIGHLIGHT}`)) el.classList.remove(HIGHLIGHT);
    }

    function render(): void {
        const step = steps[index];
        if (!step) return;
        title.textContent = step.title;
        // Config steps carry study-authored HTML; generated steps carry plain text, escaped here.
        text.innerHTML = step.emphasis ? `<strong>${escapeHtml(step.emphasis)}</strong>` : step.text;
        circle.setAttribute('stroke-dasharray', `${((index + 1) / steps.length) * 100}, 100`);

        clearHighlights();
        if (step.highlight) {
            for (const selector of step.highlight.split(',')) {
                const target = document.querySelector<HTMLElement>(selector.trim());
                if (target) target.classList.add(HIGHLIGHT);
            }
        }
        const scrollTo = step.scrollToWithin
            && document.querySelector<HTMLElement>(step.scrollToWithin.trim());
        if (scrollTo) scrollTo.scrollIntoView({ behavior: 'smooth', block: 'center' });

        const last = index === steps.length - 1;
        nextButton.textContent = last ? 'Got it!' : 'Next';
        checkmark.classList.toggle('show', last);
    }

    function finish(): void {
        clearHighlights();
        banner.style.display = 'none';
        complete = true;
        props.onComplete();
    }

    function next(): void {
        if (complete) return;
        index += 1;
        if (index >= steps.length) {
            finish();
            return;
        }
        render();
    }

    const click = () => next();
    nextButton.addEventListener('click', click);

    return {
        start() {
            if (started) return;
            started = true;
            steps = props.steps();
            if (steps.length === 0) {
                finish();
                return;
            }
            banner.style.display = 'block';
            render();
        },
        isComplete: () => complete,
        next,
        dispose() {
            nextButton.removeEventListener('click', click);
            clearHighlights();
        },
    };
}

function requireWithin(host: HTMLElement, selector: string): HTMLElement {
    const found = host.querySelector<HTMLElement>(selector);
    if (!found) throw new Error(`tutorial banner markup is missing ${selector}`);
    return found;
}
