// @vitest-environment jsdom
import { describe, expect, test } from 'vitest';

import { mountDevBadge, mountDevicePanel } from '../../src/components/device-panel';
import type { DeviceEnv } from '../../src/lib/device-info';
import { surveyFixture } from '../helpers/dom';

const ENV: DeviceEnv = {
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    maxTouchPoints: 0,
    screenWidth: 1512,
    screenHeight: 982,
    devicePixelRatio: 2,
    colorDepth: 30,
    viewportWidth: 1280,
    viewportHeight: 800,
};

const text = (id: string) => (document.getElementById(id) as HTMLElement).textContent;

describe('device panel', () => {
    test('the intake page tells the participant what the study recorded', () => {
        surveyFixture();
        mountDevicePanel(document.body, () => ENV).render();

        expect(text('user-browser')).toBe('Chrome 120.0');
        expect(text('user-os')).toBe('macOS');
        expect(text('user-screen')).toBe('1512 × 982px');
        expect(text('user-pixel-ratio')).toBe('2x');
        expect(text('user-color')).toBe('30');
    });

    test('a page without the list is not an error', () => {
        surveyFixture();
        document.querySelectorAll('#user-browser, #user-os, #user-screen, #user-pixel-ratio, #user-color')
            .forEach((el) => el.remove());

        expect(() => mountDevicePanel(document.body, () => ENV).render()).not.toThrow();
    });

    test('the panel follows the environment at render time', () => {
        surveyFixture();
        const panel = mountDevicePanel(document.body, () => ({ ...ENV, viewportHeight: 1 }));
        panel.render();
        expect(text('user-screen')).toBe('1512 × 982px');

        const rotated = mountDevicePanel(document.body, () => ({ ...ENV, screenWidth: 982, screenHeight: 1512 }));
        rotated.render();
        expect(text('user-screen')).toBe('982 × 1512px');
    });
});

describe('dev badge', () => {
    test('dev mode marks the page, once', () => {
        surveyFixture();
        const config = { dev_mode: true } as never;

        mountDevBadge(document.body, config);
        mountDevBadge(document.body, config);

        expect(document.querySelectorAll('[data-dev-badge]')).toHaveLength(1);
        expect(document.body.querySelector('[data-dev-badge]')?.textContent).toBe('DEV MODE');
    });

    test('a study run shows no badge', () => {
        surveyFixture();
        mountDevBadge(document.body, { dev_mode: false } as never);

        expect(document.querySelector('[data-dev-badge]')).toBeNull();
    });

    test('leaving dev mode takes the badge with it', () => {
        surveyFixture();
        mountDevBadge(document.body, { dev_mode: true } as never).remove();

        expect(document.querySelector('[data-dev-badge]')).toBeNull();
    });
});
