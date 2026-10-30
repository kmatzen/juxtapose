import { detectBrowser, detectOs } from '../study-state';

export type DeviceInfo = {
    browser: string;
    browser_version: string;
    os: string;
    screen_width: number;
    screen_height: number;
    pixel_ratio: number;
    color_depth: number;
    viewport_width: number;
    viewport_height: number;
};

// Injected environment: jsdom's screen/navigator are fixed, so a test cannot fake a 4K tablet.
export type DeviceEnv = {
    userAgent: string;
    maxTouchPoints: number;
    screenWidth: number;
    screenHeight: number;
    colorDepth: number;
    devicePixelRatio: number;
    viewportWidth: number;
    viewportHeight: number;
};

export function browserEnv(): DeviceEnv {
    return {
        userAgent: navigator.userAgent,
        maxTouchPoints: navigator.maxTouchPoints,
        screenWidth: screen.width,
        screenHeight: screen.height,
        colorDepth: screen.colorDepth,
        devicePixelRatio: window.devicePixelRatio || 1,
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
    };
}

export function collectDeviceInfo(env: DeviceEnv): DeviceInfo {
    const { browser, browserVersion } = detectBrowser(env.userAgent);
    return {
        browser,
        browser_version: browserVersion,
        os: detectOs(env.userAgent, env.maxTouchPoints),
        screen_width: env.screenWidth,
        screen_height: env.screenHeight,
        pixel_ratio: env.devicePixelRatio,
        color_depth: env.colorDepth,
        viewport_width: env.viewportWidth,
        viewport_height: env.viewportHeight,
    };
}
