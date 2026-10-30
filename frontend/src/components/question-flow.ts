import type { Disposable } from '../lib/dom';
import { qa } from '../lib/dom';
import { layoutSurvey } from '../lib/layout';
import type { Viewport } from '../lib/layout';
import { isFormComplete, isSectionVisible } from '../study-state';
import type { InputConfig, QuestionConfig, Trial } from '../study-state';

export type QuestionFlowProps = {
    form: HTMLFormElement;
    submitButton: HTMLButtonElement;
    /** Something outside this component can keep Submit locked; the flow asks, it does not know why. */
    blocksSubmit: () => boolean;
    /** Why Submit is locked while the form itself is answerable, so the button can say what to do. */
    blockReason?: () => string;
    questions: () => QuestionConfig[];
    inputs: () => InputConfig[];
    viewport?: () => Viewport;
    autoAdvanceDelayMs?: number;
    /** Injectable: jsdom has no IntersectionObserver. */
    observeSections?: (sections: HTMLElement[], onVisible: (index: number) => void) => Disposable;
};

export type QuestionFlow = Disposable & {
    showTrial(trial: Trial): void;
    /** The sections this trial can answer, in config order: the submit payload is built from these. */
    visibleSections(): string[];
    /** Re-measure after a resize or orientation change. */
    layout(): void;
    validate(): void;
    navigate(direction: number): void;
    index(): number;
};

const SECTION = '.questions-container .evaluation-section';
const TUTORIAL_BLOCK = () => 'Complete the tutorial first';

/** The question block: which sections this pair answers, which one counts as current, the Submit gate, and the auto-advance after an answered group. */
export function mountQuestionFlow(host: HTMLElement, props: QuestionFlowProps): QuestionFlow {
    const container = host.querySelector<HTMLElement>('.questions-container');
    const section = host.querySelector<HTMLElement>('.questions-section');
    const previous = host.querySelector<HTMLButtonElement>('#prev-question-btn');
    const next = host.querySelector<HTMLButtonElement>('#next-question-btn');
    const sections = qa<HTMLElement>(host, SECTION);
    const delay = props.autoAdvanceDelayMs ?? 500;
    const viewport = props.viewport ?? (() => ({ width: window.innerWidth, height: window.innerHeight }));

    let current = 0;
    let visible: string[] = props.questions().map((question) => question.name);
    const timers: ReturnType<typeof setTimeout>[] = [];

    function updateButtons(): void {
        if (previous) previous.disabled = current === 0;
        if (next) next.disabled = current >= sections.length - 1;
    }

    function scrollToCurrent(smooth: boolean): void {
        const target = sections[current];
        if (!container || !target) return;
        const offset = target.getBoundingClientRect().top
            - container.getBoundingClientRect().top + container.scrollTop;
        if (typeof container.scrollTo === 'function') {
            container.scrollTo({ top: offset, behavior: smooth ? 'smooth' : 'auto' });
        } else {
            container.scrollTop = offset;
        }
    }

    function navigate(direction: number): void {
        const target = current + direction;
        if (target < 0 || target >= sections.length) return;
        current = target;
        scrollToCurrent(true);
        updateButtons();
    }

    function hidden(el: Element): boolean {
        const owner = el.closest<HTMLElement>('.evaluation-section');
        return !!owner && owner.style.display === 'none';
    }

    function radios(scope: ParentNode) {
        return qa<HTMLInputElement>(scope, 'input[type="radio"]').map((radio) => ({
            name: radio.name,
            checked: radio.checked,
            hidden: hidden(radio),
        }));
    }

    function validate(): void {
        // With no visible radio group there is nothing for this rule to gate, so it must not lock Submit.
        const allAnswered = isFormComplete(radios(props.form), true);
        if (props.blocksSubmit()) {
            props.submitButton.disabled = true;
            props.submitButton.title = (props.blockReason ?? TUTORIAL_BLOCK)();
        } else {
            props.submitButton.disabled = !allAnswered;
            props.submitButton.title = '';
        }
    }

    function layout(): void {
        if (section && sections[0]) {
            layoutSurvey({ root: document, viewport }, section, sections[0]);
        }
    }

    function showTrial(trial: Trial): void {
        const shown: string[] = [];
        for (const question of props.questions()) {
            const el = host.querySelector<HTMLElement>(`#${question.name}-evaluation`);
            if (!el) continue;
            const isVisible = isSectionVisible(question, trial, props.inputs());
            el.style.display = isVisible ? 'block' : 'none';
            if (isVisible) shown.push(question.name);
            // A hidden required field would lock Submit on a question the participant cannot see.
            if (!isVisible) {
                for (const input of el.querySelectorAll('input[required]')) input.removeAttribute('required');
            }
        }

        visible = shown;
        current = 0;
        layout();
        if (container) container.scrollTop = 0;
        updateButtons();
        validate();
    }

    const change = (event: Event) => {
        const input = event.target as HTMLInputElement | null;
        if (input?.type !== 'radio') return;
        validate();

        const index = sections.findIndex((owner) => owner.contains(input));
        if (index < 0) return;
        if (!isFormComplete(radios(sections[index]), true)) return;

        // A beat of delay so the participant sees the selection they just made land.
        timers.push(setTimeout(() => {
            if (current !== index) return;
            if (index < sections.length - 1) {
                navigate(1);
            } else {
                props.submitButton.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }, delay));
    };
    props.form.addEventListener('change', change);

    const navPrevious = () => navigate(-1);
    const navNext = () => navigate(1);
    previous?.addEventListener('click', navPrevious);
    next?.addEventListener('click', navNext);

    const observer = props.observeSections?.(sections, (index) => {
        current = index;
        updateButtons();
    });
    const tutorialDone = () => validate();
    document.addEventListener('jx:tutorial-complete', tutorialDone);

    updateButtons();
    validate();

    return {
        showTrial,
        visibleSections: () => visible,
        layout,
        validate,
        navigate,
        index: () => current,
        dispose() {
            for (const timer of timers.splice(0)) clearTimeout(timer);
            props.form.removeEventListener('change', change);
            previous?.removeEventListener('click', navPrevious);
            next?.removeEventListener('click', navNext);
            document.removeEventListener('jx:tutorial-complete', tutorialDone);
            observer?.dispose();
        },
    };
}

/** Scroll position is the "current question", so the observer reports the section in view. */
export function observeSectionsIn(
    container: HTMLElement | null,
    sections: HTMLElement[],
    onVisible: (index: number) => void,
): Disposable {
    if (typeof IntersectionObserver === 'undefined') {
        return { dispose() {} };
    }
    const observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
            if (!entry.isIntersecting || entry.intersectionRatio <= 0.3) continue;
            const index = sections.indexOf(entry.target as HTMLElement);
            if (index !== -1) onVisible(index);
        }
    }, { root: container, threshold: [0.3], rootMargin: '-50px 0px -50px 0px' });
    sections.forEach((section) => observer.observe(section));
    return { dispose: () => observer.disconnect() };
}
