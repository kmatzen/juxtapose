// @vitest-environment jsdom
import { beforeEach, expect, test } from 'vitest';

import { mountConditioningTiles } from '../../src/components/conditioning-tiles';
import { maskInput } from '../../src/study-state';
import type { InputConfig, Trial } from '../../src/study-state';

/** survey.ts picked the mask with `inputs.find(i => i.type === 'image')`, so a study with a second
 * image input listed ahead of `mask_url` painted that picture in the mask tile, silently. */
const CONTEXT: InputConfig = { name: 'context', type: 'image', column: 'context_url', label: 'Context' };
const MASK: InputConfig = { name: 'mask', type: 'image', column: 'mask_url', label: 'Mask' };
const GALLERY: InputConfig = { name: 'identity', type: 'image_gallery', column: 'identity_urls' };

const PAGE = `
  <div id="survey-section">
    <div id="identity-section" style="display: none;"><div id="identity-images"></div></div>
    <div class="image-box"><img id="mask-image" class="mask-tile" /></div>
    <div class="image-box"><img id="image-a" /></div>
    <div class="image-box"><img id="image-b" /></div>
  </div>`;

const trial: Trial = {
    id: 1,
    prompt: 'p',
    method_a: 'a',
    method_b: 'b',
    image_a_url: 'https://img/a.png',
    image_b_url: 'https://img/b.png',
    total_pairs: 2,
    context_url: 'https://img/context.png',
    mask_url: 'https://img/mask.png',
};

const settle = () => new Promise((resolve) => { setTimeout(resolve, 0); });

test('the mask is the input named mask, wherever it is listed', () => {
    expect(maskInput([CONTEXT, MASK])?.column).toBe('mask_url');
    expect(maskInput([MASK, CONTEXT])?.column).toBe('mask_url');
});

test('a study that names no input mask keeps the old type-based pick', () => {
    expect(maskInput([CONTEXT])?.column).toBe('context_url');
});

test('a study with no image input has no mask', () => {
    expect(maskInput([GALLERY, CONTEXT])).toBeNull();
});

test('the mask tile shows the mask, not the image input listed before it', async () => {
    document.body.innerHTML = PAGE;
    const root = document.getElementById('survey-section') as HTMLElement;
    const inputs = [CONTEXT, MASK];
    const tiles = mountConditioningTiles(root, {
        lightbox: { open: () => undefined, close: () => undefined, dispose: () => undefined },
        galleryInput: () => null,
        maskInput: () => maskInput(inputs),
        outputImages: () => [document.getElementById('image-a'), document.getElementById('image-b')]
            .filter(Boolean) as HTMLImageElement[],
    });

    tiles.show(trial);
    await settle();

    expect(document.getElementById('mask-image')!.getAttribute('src')).toBe('https://img/mask.png');
    tiles.dispose();
});
