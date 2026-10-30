export type Viewport = { width: number; height: number };

export type LayoutTarget = {
    root: ParentNode;
    viewport: () => Viewport;
};

/** Fit the page to one viewport: the questions block gets 150% of one measured question, the tiles get a share of the viewport height. */
export function layoutSurvey(
    target: LayoutTarget,
    questionsSection: HTMLElement,
    firstQuestion: HTMLElement,
): void {
    const { root, viewport } = target;
    const visualSection = root.querySelector<HTMLElement>('.visual-content-section');
    if (!visualSection) return;

    // Measured, not styled: the question block's height depends on the study's question labels.
    questionsSection.style.height = 'auto';
    questionsSection.style.maxHeight = `${Math.floor(firstQuestion.offsetHeight * 1.5)}px`;

    visualSection.style.maxHeight = 'none';
    visualSection.style.minHeight = 'auto';

    // Half the viewport is the image budget; 80% of it leaves the prompt and titles room to breathe.
    const images = Math.floor(viewport().height * 0.5);
    for (const tile of visualSection.querySelectorAll<HTMLElement>('.tile-image')) {
        tile.style.maxHeight = `${Math.max(Math.floor(images * 0.8), 200)}px`;
        tile.style.width = 'auto';
        tile.style.height = 'auto';
        tile.style.objectFit = 'contain';
    }

    for (const identity of visualSection.querySelectorAll<HTMLElement>('.identity-image, .identity-stacked-image')) {
        identity.style.maxHeight = `${Math.floor(images / 3)}px`;
        identity.style.minWidth = '50px';
        identity.style.minHeight = '50px';
        identity.style.width = 'auto';
        identity.style.objectFit = 'contain';
    }
}
