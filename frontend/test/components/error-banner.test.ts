import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { mountErrorBanner, type ErrorBanner } from '../../src/components/error-banner';
import { mount, surveyFixture } from '../helpers/dom';

let banner: ErrorBanner;
const bannerNodes = () => document.querySelectorAll('.error-message');

beforeEach(() => {
    vi.useFakeTimers();
    surveyFixture();
    banner = mount(mountErrorBanner, document.body, {
        activeSection: () => document.querySelector<HTMLElement>('.section.active'),
    });
});

afterEach(() => {
    vi.useRealTimers();
});

const shown = () => document.querySelector('.error-message.show');

describe('the error banner', () => {
    it('appears in the section the participant is looking at', () => {
        banner.show('Failed to submit');
        const node = shown() as HTMLElement;
        expect(node.textContent).toBe('Failed to submit');
        expect(node.closest('#demographics-section')).not.toBeNull();
    });

    it('follows the page into the survey section', () => {
        document.getElementById('demographics-section')?.classList.remove('active');
        document.getElementById('survey-section')?.classList.add('active');
        banner.show('Network error');
        expect((shown() as HTMLElement).closest('#survey-section')).not.toBeNull();
    });

    it('reuses one node, so a burst of failures does not stack banners', () => {
        banner.show('first');
        banner.show('second');
        banner.show('third');
        expect(bannerNodes()).toHaveLength(1);
        expect(shown()?.textContent).toBe('third');
    });

    it('keeps participant text as text', () => {
        banner.show('<img src=x onerror=alert(1)>');
        expect((shown() as HTMLElement).querySelector('img')).toBeNull();
        expect((shown() as HTMLElement).textContent).toContain('onerror');
    });

    it('hides itself after the timeout and shows again on the next failure', () => {
        banner.show('gone in five');
        vi.advanceTimersByTime(5000);
        expect(shown()).toBeNull();
        banner.show('again');
        expect(shown()?.textContent).toBe('again');
    });

    it('restarts the timer on a second failure instead of hiding early', () => {
        banner.show('first');
        vi.advanceTimersByTime(4000);
        banner.show('second');
        vi.advanceTimersByTime(4000);
        expect(shown()?.textContent).toBe('second');
        vi.advanceTimersByTime(1000);
        expect(shown()).toBeNull();
    });

    it('honours a shorter timeout', () => {
        const short = mount(mountErrorBanner, document.body, {
            activeSection: () => document.querySelector('.section.active'),
            autoHideMs: 100,
        });
        short.show('brief');
        vi.advanceTimersByTime(100);
        expect(document.querySelector('.error-message.show')).toBeNull();
    });

    it('is a no-op with no section, where the old code threw', () => {
        document.querySelectorAll('.section.active').forEach((s) => s.classList.remove('active'));
        expect(() => banner.show('nowhere to show')).not.toThrow();
    });

    it('detaches its timer on dispose', () => {
        banner.show('pending');
        banner.dispose();
        expect(() => vi.advanceTimersByTime(10_000)).not.toThrow();
        expect(bannerNodes()).toHaveLength(0);
    });
});
