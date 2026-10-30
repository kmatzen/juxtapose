import type { Disposable } from '../lib/dom';
import { qa } from '../lib/dom';
import {
    IDENTITY_COLORS,
    buildOverlayRgba,
    extractIdentityMasks,
    stackedSliceBands,
} from '../study-state';
import type { BinaryMask, InputConfig, MaskSet, Trial } from '../study-state';
import type { Lightbox } from './lightbox';

export type ConditioningProps = {
    lightbox: Lightbox;
    /** Which trial column carries the identity sheet / the spatial mask, from the study config. */
    galleryInput: () => InputConfig | null;
    maskInput: () => InputConfig | null;
    /** The overlay paints on the A/B tiles, which this component does not own. */
    outputImages: () => HTMLImageElement[];
    tapThresholdPx?: number;
    readMask?: (image: HTMLImageElement) => MaskSet | null;
    sliceStacked?: (url: string) => Promise<string[]>;
};

export type ConditioningTiles = Disposable & {
    show(trial: Trial): void;
    clear(): void;
};

/** Conditioning tiles: identity references and the spatial mask, plus the hover/tap overlay painting one identity's region onto the output tiles. */
export function mountConditioningTiles(
    root: HTMLElement,
    props: ConditioningProps,
): ConditioningTiles {
    const section = root.querySelector<HTMLElement>('#identity-section');
    const container = root.querySelector<HTMLElement>('#identity-images');
    const maskTile = root.querySelector<HTMLImageElement>('#mask-image');
    const threshold = props.tapThresholdPx ?? 10;
    const readMask = props.readMask ?? canvasMaskReader;
    const sliceStacked = props.sliceStacked ?? canvasStackedSlicer;

    let masks: MaskSet = {};
    let activeIndex: number | null = null;
    let touchStart: { x: number; y: number } | null = null;
    let bound: (() => void)[] = [];
    let generation = 0;

    function identityImages(): HTMLImageElement[] {
        return qa<HTMLImageElement>(root, '.identity-image');
    }

    function removeOverlays(): void {
        for (const overlay of qa(root, '.mask-overlay')) overlay.remove();
    }

    function hideOverlays(): void {
        for (const overlay of qa<HTMLElement>(root, '.mask-overlay')) overlay.style.display = 'none';
        activeIndex = null;
    }

    function clear(): void {
        for (const unbind of bound.splice(0)) unbind();
        identityImages().forEach((image) => image.remove());
        masks = {};
        activeIndex = null;
        touchStart = null;
        removeOverlays();
        if (maskTile) {
            // Removing the attribute avoids resolving an empty src against the page URL.
            maskTile.removeAttribute('src');
            maskTile.onclick = null;
            maskTile.onload = null;
        }
    }

    function paintOverlay(target: HTMLImageElement, mask: BinaryMask, index: number): void {
        const box = target.parentElement;
        if (!box) return;
        let overlay = box.querySelector<HTMLCanvasElement>('.mask-overlay');
        if (!overlay) {
            overlay = document.createElement('canvas');
            overlay.className = 'mask-overlay';
            overlay.style.position = 'absolute';
            overlay.style.pointerEvents = 'none';
            overlay.style.zIndex = '10';
            box.style.position = 'relative';
            box.append(overlay);
        }

        const imgRect = target.getBoundingClientRect();
        const boxRect = box.getBoundingClientRect();
        overlay.style.left = `${imgRect.left - boxRect.left}px`;
        overlay.style.top = `${imgRect.top - boxRect.top}px`;

        // The canvas holds the mask at native resolution; CSS scales it down, so edges stay sharp.
        overlay.width = mask.width;
        overlay.height = mask.height;
        overlay.style.width = `${target.clientWidth}px`;
        overlay.style.height = `${target.clientHeight}px`;

        // An unpainted overlay is transparent, so showing it never depends on the paint succeeding.
        overlay.style.display = 'block';
        const ctx = overlay.getContext('2d');
        if (!ctx) return;
        ctx.clearRect(0, 0, overlay.width, overlay.height);
        const painted = ctx.createImageData(mask.width, mask.height);
        painted.data.set(buildOverlayRgba(mask, IDENTITY_COLORS[index] ?? [255, 255, 255]));
        ctx.putImageData(painted, 0, 0);
    }

    function showOverlay(index: number): void {
        const mask = masks[index];
        if (!mask) return;
        for (const image of props.outputImages()) {
            if (image.complete) paintOverlay(image, mask, index);
        }
        activeIndex = index;
    }

    function bindIdentity(image: HTMLImageElement, index: number, label: string): void {
        image.className = 'identity-image';
        image.setAttribute('data-identity-index', String(index));
        image.setAttribute('role', 'button');
        image.setAttribute(
            'aria-label',
            `Identity ${index + 1} - Hover or tap to highlight corresponding region in generated images`,
        );
        image.style.cursor = 'pointer';
        image.onclick = () => props.lightbox.open(image.src, `${label} ${index + 1}`);

        const enter = () => showOverlay(index);
        const leave = () => hideOverlays();
        const touchstart = (event: TouchEvent) => {
            const touch = event.touches[0];
            if (touch) touchStart = { x: touch.clientX, y: touch.clientY };
        };
        const touchend = (event: TouchEvent) => {
            const touch = event.changedTouches[0];
            if (!touchStart || !touch) return;
            const moved = Math.hypot(touch.clientX - touchStart.x, touch.clientY - touchStart.y);
            touchStart = null;
            // A drag is a scroll: only a tap in place means "show me this identity".
            if (moved >= threshold) return;
            event.preventDefault();
            if (activeIndex === index) hideOverlays();
            else showOverlay(index);
        };

        image.addEventListener('mouseenter', enter);
        image.addEventListener('mouseleave', leave);
        image.addEventListener('touchstart', touchstart, { passive: true });
        image.addEventListener('touchend', touchend);
        bound.push(() => {
            image.removeEventListener('mouseenter', enter);
            image.removeEventListener('mouseleave', leave);
            image.removeEventListener('touchstart', touchstart);
            image.removeEventListener('touchend', touchend);
        });
    }

    async function renderGallery(urls: string[], label: string): Promise<void> {
        if (!container) return;
        container.innerHTML = '';
        const mine = generation;
        const slices = urls.length > 1 ? urls : await sliceStacked(urls[0]);
        if (mine !== generation) return;
        slices.forEach((src, index) => {
            const image = document.createElement('img');
            image.src = src;
            image.alt = `${label} ${index + 1}`;
            container.append(image);
            bindIdentity(image, index, label);
        });
    }

    function show(trial: Trial): void {
        const mine = ++generation;
        clear();

        const column = (input: InputConfig | null) =>
            (input ? String(trial[input.column ?? ''] ?? '') : '').trim();
        const galleryUrl = column(props.galleryInput());
        const maskUrl = column(props.maskInput());

        if (section) section.style.display = galleryUrl ? 'block' : 'none';
        for (const tile of qa<HTMLElement>(root, '.mask-tile')) {
            tile.style.display = maskUrl ? '' : 'none';
        }

        if (galleryUrl) void renderGallery(galleryUrl.split(',').map((u) => u.trim()).filter(Boolean),
            props.galleryInput()?.label ?? 'Reference');

        if (maskUrl && maskTile) {
            maskTile.crossOrigin = 'anonymous';
            maskTile.onclick = () => props.lightbox.open(maskUrl, props.maskInput()?.label ?? 'Mask');
            maskTile.onload = () => {
                if (mine !== generation) return;
                // A mask the browser will not hand over (CORS) leaves the feature off, not the app broken.
                masks = readMask(maskTile) ?? {};
            };
            maskTile.src = maskUrl;
        }
    }

    let docTouchStart: { x: number; y: number } | null = null;
    const onDocTouchStart = (event: TouchEvent) => {
        const touch = event.touches[0];
        if (touch) docTouchStart = { x: touch.clientX, y: touch.clientY };
    };
    const onDocTouchEnd = (event: TouchEvent) => {
        const touch = event.changedTouches[0];
        if (!docTouchStart || activeIndex === null || !touch) return;
        const target = event.target as HTMLElement | null;
        if (target?.closest?.('.identity-image')) {
            docTouchStart = null;
            return;
        }
        if (Math.hypot(touch.clientX - docTouchStart.x, touch.clientY - docTouchStart.y) < threshold) {
            hideOverlays();
        }
        docTouchStart = null;
    };
    document.addEventListener('touchstart', onDocTouchStart, { passive: true });
    document.addEventListener('touchend', onDocTouchEnd, { passive: true });

    return {
        show,
        clear,
        dispose() {
            generation += 1;
            clear();
            document.removeEventListener('touchstart', onDocTouchStart);
            document.removeEventListener('touchend', onDocTouchEnd);
        },
    };
}

function canvasMaskReader(image: HTMLImageElement): MaskSet | null {
    const width = image.naturalWidth || image.width;
    const height = image.naturalHeight || image.height;
    if (!width || !height) return null;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    try {
        ctx.drawImage(image, 0, 0);
        return extractIdentityMasks(ctx.getImageData(0, 0, width, height).data, width, height);
    } catch (error) {
        console.error('Failed to process mask for overlays:', (error as Error).message);
        return null;
    }
}

async function canvasStackedSlicer(url: string): Promise<string[]> {
    const image = await loadImage(url);
    if (!image) return [];
    const bands = stackedSliceBands(image.width, image.height);
    const canvas = document.createElement('canvas');
    canvas.width = image.width;
    const ctx = canvas.getContext('2d');
    if (!ctx) return [];
    const out: string[] = [];
    for (const band of bands) {
        // Assigning the height is what clears the canvas between bands.
        canvas.height = band.height;
        ctx.drawImage(image, 0, band.y, image.width, band.height, 0, 0, image.width, band.height);
        out.push(canvas.toDataURL());
    }
    return out;
}

function loadImage(url: string): Promise<HTMLImageElement | null> {
    return new Promise((resolve) => {
        const image = new Image();
        image.crossOrigin = 'anonymous';
        image.onload = () => resolve(image);
        image.onerror = () => {
            console.error('Failed to load gallery image:', url);
            resolve(null);
        };
        image.src = url;
    });
}
