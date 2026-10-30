import { beforeEach, describe, expect, it } from 'vitest';

import { mountLightbox, type Lightbox } from '../../src/components/lightbox';
import { mount, surveyFixture } from '../helpers/dom';

let lightbox: Lightbox;
const root = () => document.getElementById('image-lightbox') as HTMLElement;
const image = () => document.getElementById('lightbox-image') as HTMLImageElement;
const caption = () => document.querySelector('.lightbox-caption') as HTMLElement;
const shown = () => root().classList.contains('show');
const pressEscape = () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

beforeEach(() => {
    surveyFixture();
    lightbox = mount(mountLightbox, document.getElementById('image-lightbox') as HTMLElement);
});

describe('the image lightbox', () => {
    it('shows the full image with its caption', () => {
        lightbox.open('https://img/a.png', 'Image A');
        expect(image().src).toBe('https://img/a.png');
        expect(caption().textContent).toBe('Image A');
        expect(shown()).toBe(true);
    });

    it('dismisses on Escape, the close button, and a backdrop click', () => {
        lightbox.open('https://img/a.png', 'Image A');
        pressEscape();
        expect(shown()).toBe(false);

        lightbox.open('https://img/b.png', 'Image B');
        document.querySelector<HTMLElement>('.lightbox-close')?.click();
        expect(shown()).toBe(false);

        lightbox.open('https://img/b.png', 'Image B');
        root().dispatchEvent(new Event('click'));
        expect(shown()).toBe(false);
    });

    it('keeps the image when a click lands inside the card', () => {
        lightbox.open('https://img/a.png', 'Image A');
        (root().querySelector('.lightbox-content') as HTMLElement).dispatchEvent(
            new Event('click', { bubbles: true }),
        );
        expect(shown()).toBe(true);
    });

    it('ignores Escape while it is closed', () => {
        pressEscape();
        expect(shown()).toBe(false);
    });

    it('replaces the previous image on the next open', () => {
        lightbox.open('https://img/a.png', 'Image A');
        lightbox.open('https://img/b.png', 'Image B');
        expect(image().src).toBe('https://img/b.png');
        expect(caption().textContent).toBe('Image B');
    });

    it('keeps participant captions out of markup', () => {
        lightbox.open('https://img/a.png', '<img src=x onerror=alert(1)>');
        expect(caption().querySelector('img')).toBeNull();
    });

    it('stops listening once disposed', () => {
        lightbox.open('https://img/a.png', 'Image A');
        lightbox.dispose();
        expect(shown()).toBe(false);
        lightbox.open('https://img/b.png', 'Image B');
        document.querySelector<HTMLElement>('.lightbox-close')?.click();
        expect(shown()).toBe(true);
    });
});
