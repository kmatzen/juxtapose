import { el, type Disposable } from '../lib/dom';

export type ErrorBannerProps = {
    /** Resolved at show() time: the banner belongs to the section the participant is looking at. */
    activeSection: () => HTMLElement | null;
    autoHideMs?: number;
};

export type ErrorBanner = Disposable & {
    show(message: string): void;
    hide(): void;
};

export function mountErrorBanner(
    host: HTMLElement,
    { activeSection, autoHideMs = 5000 }: ErrorBannerProps,
): ErrorBanner {
    const node = el('div', { class: 'error-message', role: 'alert' });
    let timer: ReturnType<typeof setTimeout> | null = null;

    const hide = (): void => {
        node.classList.remove('show');
        if (timer !== null) {
            clearTimeout(timer);
            timer = null;
        }
    };

    return {
        show(message: string): void {
            const section = activeSection();
            // No section means the page is mid-navigation; a banner has nowhere to be seen.
            if (!section) return;
            if (!node.isConnected) section.prepend(node);
            node.textContent = message;
            hide();
            node.classList.add('show');
            timer = setTimeout(hide, autoHideMs);
        },
        hide,
        dispose() {
            hide();
            node.remove();
        },
    };
}
