import { beforeEach, describe, expect, it, vi } from 'vitest';

import { mountRetakeModal, type RetakeModal } from '../../src/components/retake-modal';
import { byText, mount, surveyFixture } from '../helpers/dom';

const MODAL = () => document.getElementById('retake-modal') as HTMLElement;
const open = () => MODAL().classList.contains('show');

let modal: RetakeModal;

beforeEach(() => {
    surveyFixture();
    document.getElementById('retake-modal')?.remove();
    document.documentElement.className = '';
    modal = mount(mountRetakeModal, document.body, {});
});

describe('the retake question', () => {
    it('states the consequence before asking for the decision', () => {
        modal.ask();
        expect(byText(MODAL(), 'Survey Already Completed')).toBeTruthy();
        expect(byText(MODAL(), 'If you continue, your previous responses will be overwritten.')).toBeTruthy();
    });

    it('resolves true only on Continue and Retake', async () => {
        const asked = modal.ask();
        byText(MODAL(), 'Continue and Retake').click();
        expect(await asked).toBe(true);
        expect(open()).toBe(false);
    });

    it('resolves false on Cancel', async () => {
        const asked = modal.ask();
        byText(MODAL(), 'Cancel').click();
        expect(await asked).toBe(false);
    });

    it('treats a backdrop click as Cancel, since clicking away is not consent', async () => {
        const asked = modal.ask();
        MODAL().dispatchEvent(new Event('click'));
        expect(await asked).toBe(false);
    });

    it('ignores clicks inside the card, which are not backdrop clicks', async () => {
        const asked = modal.ask();
        (MODAL().querySelector('.modal-content') as HTMLElement).dispatchEvent(new Event('click', { bubbles: true }));
        expect(open()).toBe(true);
        byText(MODAL(), 'Cancel').click();
        expect(await asked).toBe(false);
    });

    it('refuses a second question while one is open', async () => {
        modal.ask();
        await expect(modal.ask()).rejects.toThrow(/already open/);
    });

    it('reports the decision to the caller as well as to the promise', async () => {
        const onDecide = vi.fn();
        const slot = document.createElement('div');
        document.body.append(slot);
        const withCallback = mount(mountRetakeModal, slot, { onDecide });
        withCallback.ask();
        byText(slot, 'Cancel').click();
        expect(onDecide).toHaveBeenCalledWith(false);
    });
});

describe('scroll lock while the question is open', () => {
    it('locks the page on open and releases it on the answer', async () => {
        const asked = modal.ask();
        expect(document.documentElement.classList.contains('modal-open')).toBe(true);
        byText(MODAL(), 'Cancel').click();
        await asked;
        expect(document.documentElement.classList.contains('modal-open')).toBe(false);
    });

    it('publishes the scroll offset the page must return to', async () => {
        Object.defineProperty(window, 'scrollY', { value: 240, configurable: true });
        const asked = modal.ask();
        expect(document.documentElement.style.getPropertyValue('--modal-scroll-y')).toBe('240px');
        byText(MODAL(), 'Continue and Retake').click();
        await asked;
        expect(document.documentElement.classList.contains('modal-open')).toBe(false);
    });

    it('unlocks on dispose, so a teardown mid-question cannot leave the page frozen', () => {
        modal.ask();
        modal.dispose();
        expect(document.documentElement.classList.contains('modal-open')).toBe(false);
    });
});

describe('dispose', () => {
    it('removes the modal and stops answering clicks', () => {
        modal.ask();
        modal.dispose();
        expect(document.getElementById('retake-modal')).toBeNull();
        expect(() => byText(document.body, 'Cancel')).toThrow();
    });
});
