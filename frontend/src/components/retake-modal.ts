import { el, on, toggleClass, type Disposable } from '../lib/dom';

export type RetakeModalProps = {
    onDecide?: (continueAndRetake: boolean) => void;
};

export type RetakeModal = Disposable & {
    ask(): Promise<boolean>;
};

const COPY = {
    title: 'Survey Already Completed',
    line1: 'It looks like you have already taken this survey with this email address.',
    warning: 'If you continue, your previous responses will be overwritten.',
    question: 'Do you want to continue and retake the survey?',
    cancel: 'Cancel',
    confirm: 'Continue and Retake',
};

// ask() resolves only on an answer: a caller must never delete on a path that got none.
export function mountRetakeModal(host: HTMLElement, props: RetakeModalProps = {}): RetakeModal {
    const confirm = el('button', { id: 'retake-confirm', class: 'btn-primary' }, COPY.confirm);
    const cancel = el('button', { id: 'retake-cancel', class: 'btn-secondary' }, COPY.cancel);
    const modal = el(
        'div',
        { id: 'retake-modal', class: 'modal', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'retake-title' },
        el(
            'div',
            { class: 'modal-content' },
            el('div', { class: 'modal-header' }, el('h2', { id: 'retake-title' }, COPY.title)),
            el(
                'div',
                { class: 'modal-body' },
                el('p', {}, COPY.line1),
                el('p', {}, el('strong', {}, COPY.warning)),
                el('p', {}, COPY.question),
            ),
            el('div', { class: 'modal-footer' }, cancel, confirm),
        ),
    );
    host.append(modal);

    let settle: ((go: boolean) => void) | null = null;
    let lockedAt: number | null = null;

    // The viewport-fixed backdrop needs the body out of flow: Chrome scrolls an overflow:hidden
    // viewport when the wheel lands on a position:fixed element, which a backdrop is.
    const lock = (): void => {
        lockedAt = window.scrollY;
        document.documentElement.style.setProperty('--modal-scroll-y', `${lockedAt}px`);
        document.documentElement.classList.add('modal-open');
    };

    const unlock = (): void => {
        if (lockedAt === null) return;
        const scrollY = lockedAt;
        lockedAt = null;
        document.documentElement.classList.remove('modal-open');
        // The document has nothing to scroll while the body is out of flow, so the restore lands a frame later.
        requestAnimationFrame(() => window.scrollTo(0, scrollY));
    };

    const finish = (go: boolean): void => {
        if (!settle) return;
        const resolve = settle;
        settle = null;
        toggleClass(modal, 'show', false);
        unlock();
        props.onDecide?.(go);
        resolve(go);
    };

    const detach = [
        on(confirm, 'click', () => finish(true)),
        on(cancel, 'click', () => finish(false)),
        on(modal, 'click', (event) => {
            if (event.target === modal) finish(false);
        }),
    ];

    return {
        ask() {
            // Two open questions would strand the first promise and leave the backdrop up forever.
            if (settle) return Promise.reject(new Error('a retake question is already open'));
            lock();
            toggleClass(modal, 'show', true);
            return new Promise<boolean>((resolve) => {
                settle = resolve;
            });
        },
        dispose() {
            detach.forEach((off) => off());
            unlock();
            modal.remove();
        },
    };
}
