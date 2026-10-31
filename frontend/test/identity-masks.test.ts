import { describe, expect, test } from 'vitest';

import {
    IDENTITY_COLORS,
    buildOverlayRgba,
    countStackedSegments,
    extractIdentityMasks,
    stackedSliceBands,
} from '../src/study-state';

function rgbaOf(pixels: [number, number, number][]): Uint8ClampedArray {
    const out = new Uint8ClampedArray(pixels.length * 4);
    pixels.forEach(([r, g, b], i) => {
        out[i * 4] = r;
        out[i * 4 + 1] = g;
        out[i * 4 + 2] = b;
        out[i * 4 + 3] = 255;
    });
    return out;
}

describe('extractIdentityMasks', () => {
    test('one mask per identity colour, matching pixels claimed by exactly one', () => {
        const [red, green] = IDENTITY_COLORS;
        const rgba = rgbaOf([red, green, red, [0, 0, 0]] as [number, number, number][]);

        const masks = extractIdentityMasks(rgba, 2, 2);

        expect(Object.keys(masks)).toHaveLength(IDENTITY_COLORS.length);
        expect(Array.from(masks[0].data)).toEqual([255, 0, 255, 0]);
        expect(Array.from(masks[1].data)).toEqual([0, 255, 0, 0]);
        expect(masks[0].matchCount).toBe(2);
        expect(masks[0].width).toBe(2);
        expect(masks[0].height).toBe(2);
    });

    test('antialiased edge pixels within tolerance still belong to their region', () => {
        const [red] = IDENTITY_COLORS;
        const edge = [red[0] - 9, red[1] + 8, red[2] - 8];
        const far = [red[0] - 40, red[1], red[2]];

        const masks = extractIdentityMasks(rgbaOf([edge, far] as [number, number, number][]), 2, 1);

        expect(Array.from(masks[0].data)).toEqual([255, 0]);
    });

    test('an alpha-only difference does not break a match, and alpha is not part of it', () => {
        const rgba = new Uint8ClampedArray([255, 0, 0, 0, 255, 0, 0, 255]);
        const masks = extractIdentityMasks(rgba, 2, 1);
        expect(Array.from(masks[0].data)).toEqual([255, 255]);
    });
});

describe('buildOverlayRgba', () => {
    test('masked pixels get the identity colour at 100 alpha, the rest is transparent', () => {
        const mask = { data: new Uint8Array([255, 0, 128]), width: 3, height: 1, matchCount: 2 };

        const rgba = buildOverlayRgba(mask, [255, 0, 0]);

        expect(Array.from(rgba.slice(0, 4))).toEqual([255, 0, 0, 100]);
        expect(Array.from(rgba.slice(4, 8))).toEqual([0, 0, 0, 0]);
        expect(rgba[11]).toBe(100);
        expect(rgba).toHaveLength(12);
    });
});

describe('countStackedSegments', () => {
    test('a sheet of square segments is height over width', () => {
        expect(countStackedSegments(200, 200)).toBe(1);
        expect(countStackedSegments(200, 800)).toBe(4);
    });

    test('a ragged bottom row does not make a partial segment', () => {
        expect(countStackedSegments(200, 550)).toBe(3);
    });
});

/** Audit 6 F11: the slicer cut one square per segment, so a sheet of non-square panels sliced across the panels. */
describe('stackedSliceBands', () => {
    test('a sheet of square panels is unchanged', () => {
        expect(stackedSliceBands(200, 800)).toEqual([
            { y: 0, height: 200 },
            { y: 200, height: 200 },
            { y: 400, height: 200 },
            { y: 600, height: 200 },
        ]);
    });

    test('a 512x768 sheet cuts at its own height over segments', () => {
        expect(stackedSliceBands(512, 768)).toEqual([
            { y: 0, height: 384 },
            { y: 384, height: 384 },
        ]);
    });

    test('the bands tile the sheet exactly, ragged height included', () => {
        const bands = stackedSliceBands(200, 550);

        expect(bands).toHaveLength(3);
        expect(bands[0].y).toBe(0);
        expect(bands[2].y + bands[2].height).toBe(550);
        bands.reduce((y, band) => {
            expect(band.y).toBe(y);
            return band.y + band.height;
        }, 0);
    });

    test('a sheet shorter than one panel is one band, not zero', () => {
        expect(stackedSliceBands(400, 120)).toEqual([{ y: 0, height: 120 }]);
    });
});
