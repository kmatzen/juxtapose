import { beforeEach, describe, expect, it } from 'vitest';

import { collectDeviceInfo, renderDeviceInfo, type DeviceEnv } from '../../src/lib/device-info';
import { surveyFixture } from '../helpers/dom';

const CHROME_MAC =
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';

const IPHONE =
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

const env = (overrides: Partial<DeviceEnv> = {}): DeviceEnv => ({
    userAgent: CHROME_MAC,
    maxTouchPoints: 0,
    screenWidth: 2560,
    screenHeight: 1440,
    colorDepth: 24,
    devicePixelRatio: 2,
    viewportWidth: 1440,
    viewportHeight: 900,
    ...overrides,
});

describe('collectDeviceInfo', () => {
    it('parses browser and OS from the user agent', () => {
        const info = collectDeviceInfo(env());
        expect(info.browser).toBe('Chrome');
        expect(info.browser_version).toBe('126.0');
        expect(info.os).toBe('macOS');
    });

    it('calls a touch device out of the desktop path', () => {
        expect(collectDeviceInfo(env({ userAgent: IPHONE, maxTouchPoints: 5 })).os).toContain('iOS');
    });

    it('reports the screen and viewport separately', () => {
        expect(collectDeviceInfo(env())).toMatchObject({
            screen_width: 2560,
            screen_height: 1440,
            viewport_width: 1440,
            viewport_height: 900,
            pixel_ratio: 2,
            color_depth: 24,
        });
    });
});

describe('renderDeviceInfo', () => {
    beforeEach(() => surveyFixture());

    it('fills the data-collection notice', () => {
        renderDeviceInfo(document, collectDeviceInfo(env()));
        const text = (id: string) => document.getElementById(id)?.textContent;
        expect(text('user-browser')).toBe('Chrome 126.0');
        expect(text('user-os')).toBe('macOS');
        expect(text('user-screen')).toBe('2560 × 1440px');
        expect(text('user-pixel-ratio')).toBe('2x');
        expect(text('user-color')).toBe('24');
    });

    it('leaves the survey page alone, where the notice is not rendered', () => {
        document.body.innerHTML = '<div id="survey-form"></div>';
        expect(() => renderDeviceInfo(document, collectDeviceInfo(env()))).not.toThrow();
    });
});
