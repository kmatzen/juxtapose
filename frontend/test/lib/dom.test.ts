import { beforeEach, describe, expect, it, vi } from 'vitest';

import { byId, compose, el, need, on, qa, q, setVisible, toggleClass } from '../../src/lib/dom';

describe('el', () => {
    it('omits absent attributes so they do not render as the string undefined', () => {
        const node = el('img', { src: 'a.png', alt: null, loading: undefined });
        expect(node.getAttribute('src')).toBe('a.png');
        expect(node.hasAttribute('alt')).toBe(false);
        expect(node.hasAttribute('loading')).toBe(false);
    });

    it('renders a true flag as a bare attribute', () => {
        expect(el('input', { disabled: true }).outerHTML).toContain('disabled=""');
    });

    it('appends children and keeps text out of markup', () => {
        const payload = '<img src=x onerror=alert(1)>';
        const node = el('p', {}, payload);
        expect(node.textContent).toBe(payload);
        expect(node.querySelector('img')).toBeNull();
    });
});

describe('queries', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="a" class="x"><span class="x">1</span></div>';
    });

    it('scopes to the given root', () => {
        const root = document.getElementById('a') as HTMLElement;
        expect(q(root, '.x')?.textContent).toBe('1');
        expect(q(document.body, '#a .x')?.textContent).toBe('1');
        expect(qa(root, '.x')).toHaveLength(1);
        expect(byId(document.body, 'a')?.id).toBe('a');
    });

    it('needs throws at the mount, naming the selector', () => {
        expect(() => need(document.body, '#missing')).toThrow(/missing element: #missing/);
    });
});

describe('on', () => {
    it('hands back a detach that stops the handler', () => {
        const seen = vi.fn();
        const detach = on(document.body, 'click', seen);
        document.body.click();
        detach();
        document.body.click();
        expect(seen).toHaveBeenCalledTimes(1);
    });
});

describe('visibility', () => {
    it('sets inline display, the axis the template hides on', () => {
        const node = el('div');
        setVisible(node, true);
        expect(node.style.display).toBe('block');
        setVisible(node, true, 'flex');
        expect(node.style.display).toBe('flex');
        setVisible(node, false);
        expect(node.style.display).toBe('none');
    });

    it('toggles a class both ways', () => {
        const node = el('div');
        toggleClass(node, 'show', true);
        expect(node.classList.contains('show')).toBe(true);
        toggleClass(node, 'show', false);
        expect(node.classList.contains('show')).toBe(false);
    });
});

describe('compose', () => {
    it('disposes every part in order', () => {
        const order: string[] = [];
        compose([{ dispose: () => order.push('a') }, { dispose: () => order.push('b') }]).dispose();
        expect(order).toEqual(['a', 'b']);
    });
});
