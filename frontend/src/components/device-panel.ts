import type { DeviceEnv } from '../lib/device-info';
import type { SurveyConfig } from '../lib/session-api';
import { detectBrowser, detectOs } from '../study-state';

export type DevicePanel = { render(): void };
/** The "your setup" list on the intake page. Display only — the POSTed snapshot is taken separately at boot, so a mid-form viewport change cannot split one participant's rows. */
export function mountDevicePanel(host: ParentNode, env: () => DeviceEnv): DevicePanel {
    function write(id: string, value: string): void {
        const el = host.querySelector<HTMLElement>(`#${id}`);
        if (el) el.textContent = value;
    }

    return {
        render() {
            const current = env();
            const { browser, browserVersion } = detectBrowser(current.userAgent);
            const os = detectOs(current.userAgent, current.maxTouchPoints);
            write('user-browser', `${browser} ${browserVersion}`);
            write('user-os', os);
            write('user-screen', `${current.screenWidth} × ${current.screenHeight}px`);
            write('user-pixel-ratio', `${current.devicePixelRatio}x`);
            write('user-color', String(current.colorDepth));
        },
    };
}

export function mountDevBadge(host: HTMLElement, config: SurveyConfig | null): DisposableBadge {
    const existing = host.querySelector<HTMLElement>('[data-dev-badge]');
    if (!config?.dev_mode || existing) return { remove() {} };

    const badge = document.createElement('div');
    badge.dataset.devBadge = 'true';
    badge.style.cssText = 'position: fixed; top: 10px; right: 10px; background: #ff6b6b; color: white; padding: 10px 15px; border-radius: 5px; z-index: 10000; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.2);';
    badge.textContent = 'DEV MODE';
    host.appendChild(badge);
    return { remove: () => badge.remove() };
}

export type DisposableBadge = { remove(): void };
