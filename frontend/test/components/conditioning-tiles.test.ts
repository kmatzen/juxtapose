// @vitest-environment jsdom
import { beforeEach, describe, expect, test, vi } from 'vitest';

import { mountConditioningTiles } from '../../src/components/conditioning-tiles';
import type { ConditioningTiles } from '../../src/components/conditioning-tiles';
import type { BinaryMask, InputConfig, MaskSet, Trial } from '../../src/study-state';

const GALLERY: InputConfig = { name: 'identity', type: 'image_gallery', column: 'identity_urls', label: 'Reference' };
const MASK: InputConfig = { name: 'mask', type: 'image', column: 'mask_url', label: 'Mask' };

const PAGE = `
  <div id="survey-section">
    <div id="identity-section" style="display: none;">
      <div id="identity-images"></div>
    </div>
    <div class="image-box"><img id="mask-image" class="mask-tile" /></div>
    <div class="image-box"><img id="image-a" /></div>
    <div class="image-box"><img id="image-b" /></div>
  </div>`;

const trial = (over: Partial<Trial> = {}): Trial =>
    ({
        id: 1,
        prompt: 'p',
        method_a: 'a',
        method_b: 'b',
        image_a_url: 'https://img/a.png',
        image_b_url: 'https://img/b.png',
        total_pairs: 2,
        identity_urls: 'https://img/id1.png, https://img/id2.png',
        mask_url: 'https://img/mask.png',
        ...over,
    }) as Trial;

const maskOf = (value: number): BinaryMask => ({
    data: new Uint8Array([value, 0]),
    width: 2,
    height: 1,
    matchCount: 1,
});
const masksWith = (...indices: number[]): MaskSet =>
    Object.fromEntries(indices.map((i) => [i, maskOf(255)])) as MaskSet;

type Harness = {
    root: HTMLElement;
    tiles: ConditioningTiles;
    opened: string[];
    readMask: ReturnType<typeof vi.fn>;
    sliceStacked: ReturnType<typeof vi.fn>;
    outputs: HTMLImageElement[];
};

function harness(
    over: Partial<Parameters<typeof mountConditioningTiles>[1]> = {},
): Harness {
    document.body.innerHTML = PAGE;
    const root = document.getElementById('survey-section') as HTMLElement;
    const opened: string[] = [];
    const readMask = vi.fn(() => masksWith(0, 1));
    const sliceStacked = vi.fn(async () => ['slice-0', 'slice-1']);
    const tiles = mountConditioningTiles(root, {
        lightbox: { open: (src) => opened.push(src), close: vi.fn(), dispose: vi.fn() },
        galleryInput: () => GALLERY,
        maskInput: () => MASK,
        outputImages: () =>
            [document.getElementById('image-a'), document.getElementById('image-b')]
                .filter(Boolean) as HTMLImageElement[],
        readMask,
        sliceStacked,
        ...over,
    });
    const outputs = [
        document.getElementById('image-a') as HTMLImageElement,
        document.getElementById('image-b') as HTMLImageElement,
    ];
    for (const image of outputs) {
        Object.defineProperty(image, 'complete', { value: true, configurable: true });
    }
    return { root, tiles, opened, readMask, sliceStacked, outputs };
}

const identityTiles = (root: HTMLElement) =>
    Array.from(root.querySelectorAll<HTMLImageElement>('.identity-image'));
const overlays = (root: HTMLElement) =>
    Array.from(root.querySelectorAll<HTMLCanvasElement>('canvas.mask-overlay'));

const touch = (target: EventTarget, type: string, x: number, y: number) => {
    const event = new Event(type, { bubbles: true, cancelable: true });
    Object.defineProperty(event, type === 'touchstart' ? 'touches' : 'changedTouches', {
        value: [{ clientX: x, clientY: y }],
    });
    target.dispatchEvent(event);
    return event;
};

const settle = () => new Promise((resolve) => { setTimeout(resolve, 0); });

describe('ConditioningTiles', () => {
    let h: Harness;

    beforeEach(() => {
        h = harness();
    });

    test('a comma list renders one tile per identity, indexed and labelled', async () => {
        h.tiles.show(trial());
        await settle();

        const tiles = identityTiles(h.root);
        expect(tiles).toHaveLength(2);
        expect(tiles.map((t) => t.getAttribute('data-identity-index'))).toEqual(['0', '1']);
        expect(tiles.map((t) => t.alt)).toEqual(['Reference 1', 'Reference 2']);
        expect(tiles[0].getAttribute('role')).toBe('button');
        expect(tiles[0].getAttribute('aria-label')).toContain('Identity 1');
        expect(document.getElementById('identity-section')!.style.display).toBe('block');
    });

    test('a lone url is a stacked sheet sliced into segments', async () => {
        h.tiles.show(trial({ identity_urls: 'https://img/stack.png' }));
        await settle();

        expect(h.sliceStacked).toHaveBeenCalledWith('https://img/stack.png', 2);
        expect(identityTiles(h.root).map((t) => t.getAttribute('src'))).toEqual(['slice-0', 'slice-1']);
    });

    test('the sheet is sliced by the identities the mask carries', async () => {
        // The mask is the study's own count of identities; geometry only guesses from panel shape.
        const three = harness({ readMask: vi.fn(() => masksWith(0, 1, 2)) });
        three.tiles.show(trial({ identity_urls: 'https://img/stack.png' }));
        await settle();

        expect(three.sliceStacked).toHaveBeenCalledWith('https://img/stack.png', 3);
        three.tiles.dispose();
    });

    test('a trial with no identity column hides the section', async () => {
        h.tiles.show(trial({ identity_urls: '' }));
        await settle();

        expect(document.getElementById('identity-section')!.style.display).toBe('none');
        expect(identityTiles(h.root)).toHaveLength(0);
    });

    test('the mask tile shows with the mask and hides without one', () => {
        h.tiles.show(trial());
        const mask = document.getElementById('mask-image') as HTMLImageElement;
        expect(mask.getAttribute('src')).toBe('https://img/mask.png');
        expect(mask.crossOrigin).toBe('anonymous');
        expect((h.root.querySelector('.mask-tile') as HTMLElement).style.display).not.toBe('none');

        h.tiles.show(trial({ mask_url: '' }));
        expect(mask.getAttribute('src')).toBeNull();
        expect((h.root.querySelector('.mask-tile') as HTMLElement).style.display).toBe('none');
    });

    test('tiles never persist: a conditioning-free trial clears the previous pair', async () => {
        h.tiles.show(trial());
        await settle();
        expect(identityTiles(h.root)).toHaveLength(2);

        h.tiles.show(trial({ identity_urls: '', mask_url: '' }));
        expect(identityTiles(h.root)).toHaveLength(0);
        expect((document.getElementById('mask-image') as HTMLImageElement).getAttribute('src')).toBeNull();
    });

    test('identity and mask tiles open the lightbox', async () => {
        h.tiles.show(trial());
        await settle();

        identityTiles(h.root)[1].click();
        (document.getElementById('mask-image') as HTMLImageElement).click();

        expect(h.opened).toEqual(['https://img/id2.png', 'https://img/mask.png']);
    });

    test('hovering an identity paints its region on every output tile', async () => {
        h.tiles.show(trial());
        await settle();
        const mask = document.getElementById('mask-image') as HTMLImageElement;
        mask.dispatchEvent(new Event('load'));

        identityTiles(h.root)[0].dispatchEvent(new Event('mouseenter'));

        const painted = overlays(h.root);
        expect(painted).toHaveLength(2);
        expect(painted[0].width).toBe(2);
        expect(painted[0].style.display).toBe('block');
    });

    test('a hover that lands before a tile loads paints when that tile arrives', async () => {
        h = harness();
        const [, b] = h.outputs;
        Object.defineProperty(b, 'complete', { value: false, configurable: true });
        h.tiles.show(trial());
        await settle();
        (document.getElementById('mask-image') as HTMLImageElement).dispatchEvent(new Event('load'));

        identityTiles(h.root)[0].dispatchEvent(new Event('mouseenter'));
        await settle();
        expect(overlays(h.root)).toHaveLength(1);

        b.dispatchEvent(new Event('load'));
        await settle();

        expect(overlays(h.root)).toHaveLength(2);
        expect(overlays(h.root).every((overlay) => overlay.style.display === 'block')).toBe(true);
    });

    test('a tile that arrives after the participant stopped hovering paints nothing', async () => {
        h = harness();
        const [, b] = h.outputs;
        Object.defineProperty(b, 'complete', { value: false, configurable: true });
        h.tiles.show(trial());
        await settle();
        (document.getElementById('mask-image') as HTMLImageElement).dispatchEvent(new Event('load'));

        const identity = identityTiles(h.root)[0];
        identity.dispatchEvent(new Event('mouseenter'));
        identity.dispatchEvent(new Event('mouseleave'));

        b.dispatchEvent(new Event('load'));
        await settle();

        const visible = overlays(h.root).filter((overlay) => overlay.style.display === 'block');
        expect(visible).toHaveLength(0);
    });

    test('leaving hides the overlay again', async () => {
        h.tiles.show(trial());
        await settle();
        (document.getElementById('mask-image') as HTMLImageElement).dispatchEvent(new Event('load'));
        const tile = identityTiles(h.root)[0];

        tile.dispatchEvent(new Event('mouseenter'));
        expect(overlays(h.root)[0].style.display).toBe('block');

        tile.dispatchEvent(new Event('mouseleave'));
        expect(overlays(h.root)[0].style.display).toBe('none');
    });

    test('a mask that cannot be read switches the feature off instead of breaking', async () => {
        h = harness({ readMask: vi.fn(() => null) });
        h.tiles.show(trial());
        await settle();
        (document.getElementById('mask-image') as HTMLImageElement).dispatchEvent(new Event('load'));

        identityTiles(h.root)[0].dispatchEvent(new Event('mouseenter'));
        expect(overlays(h.root)).toHaveLength(0);
    });

    test('a tap shows the region, a second tap on the same identity hides it', async () => {
        h.tiles.show(trial());
        await settle();
        (document.getElementById('mask-image') as HTMLImageElement).dispatchEvent(new Event('load'));
        const tile = identityTiles(h.root)[0];

        touch(tile, 'touchstart', 10, 10);
        const tap = touch(tile, 'touchend', 11, 11);
        expect(tap.defaultPrevented).toBe(true);
        expect(overlays(h.root)[0].style.display).toBe('block');

        touch(tile, 'touchstart', 10, 10);
        touch(tile, 'touchend', 10, 10);
        expect(overlays(h.root)[0].style.display).toBe('none');
    });

    test('a drag across an identity tile is a scroll, not a tap', async () => {
        h.tiles.show(trial());
        await settle();
        (document.getElementById('mask-image') as HTMLImageElement).dispatchEvent(new Event('load'));
        const tile = identityTiles(h.root)[0];

        touch(tile, 'touchstart', 10, 10);
        touch(tile, 'touchend', 90, 90);

        expect(overlays(h.root)).toHaveLength(0);
    });

    test('tapping outside the identity strip dismisses the overlay', async () => {
        h.tiles.show(trial());
        await settle();
        (document.getElementById('mask-image') as HTMLImageElement).dispatchEvent(new Event('load'));
        const tile = identityTiles(h.root)[0];

        touch(tile, 'touchstart', 10, 10);
        touch(tile, 'touchend', 10, 10);
        expect(overlays(h.root)[0].style.display).toBe('block');

        const outside = document.getElementById('image-a') as HTMLElement;
        touch(outside, 'touchstart', 50, 50);
        touch(outside, 'touchend', 50, 50);
        expect(overlays(h.root)[0].style.display).toBe('none');
    });

    test('a superseded stacked sheet cannot paint tiles for a trial that moved on', async () => {
        let release: () => void = () => {};
        h = harness({
            sliceStacked: vi.fn(() => new Promise<string[]>((resolve) => {
                release = () => resolve(['late-0']);
            })),
        });

        h.tiles.show(trial({ identity_urls: 'https://img/stack.png' }));
        h.tiles.show(trial({ identity_urls: '' }));
        release();
        await settle();

        expect(identityTiles(h.root)).toHaveLength(0);
    });

    test('dispose removes the tiles, the overlays and the handlers', async () => {
        h.tiles.show(trial());
        await settle();
        (document.getElementById('mask-image') as HTMLImageElement).dispatchEvent(new Event('load'));
        const tile = identityTiles(h.root)[0];
        h.tiles.dispose();

        expect(identityTiles(h.root)).toHaveLength(0);
        expect(overlays(h.root)).toHaveLength(0);
        tile.dispatchEvent(new Event('mouseenter'));
        expect(overlays(h.root)).toHaveLength(0);
    });

});
