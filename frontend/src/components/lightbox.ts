import { need, on, toggleClass, type Disposable } from '../lib/dom';

export type Lightbox = Disposable & {
    open(src: string, caption: string): void;
    close(): void;
};

export function mountLightbox(root: HTMLElement): Lightbox {
    const image = need<HTMLImageElement>(root, '#lightbox-image');
    const caption = need(root, '.lightbox-caption');
    const closeBtn = need(root, '.lightbox-close');

    const close = (): void => toggleClass(root, 'show', false);

    const detach = [
        on(closeBtn, 'click', close),
        on(root, 'click', (event) => {
            if (event.target === root) close();
        }),
        // Esc is heard on the document: the participant is looking at the image, not focused in it.
        on(document, 'keydown', (event) => {
            if ((event as KeyboardEvent).key === 'Escape' && root.classList.contains('show')) close();
        }),
    ];

    return {
        open(src: string, text: string): void {
            image.src = src;
            caption.textContent = text;
            toggleClass(root, 'show', true);
        },
        close,
        dispose() {
            detach.forEach((off) => off());
            close();
        },
    };
}
