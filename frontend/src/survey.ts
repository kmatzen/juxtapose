import { mountErrorBanner } from './components/error-banner';
import { mountLightbox } from './components/lightbox';
import { mountRetakeModal } from './components/retake-modal';
import { need } from './lib/dom';
import type { SurveySeam } from './seam';
import * as studyState from './study-state';

// Grows with each step of docs/frontend-architecture.md: the classic script's duties land here.
function mountSurveyPage(): SurveySeam {
    return {
        core: studyState,
        banner: mountErrorBanner(document.body, {
            activeSection: () => document.querySelector<HTMLElement>('.section.active'),
        }),
        lightbox: mountLightbox(need(document.body, '#image-lightbox')),
        retake: mountRetakeModal(document.body),
    };
}

function start(): void {
    window.__JX__ = mountSurveyPage();
    document.documentElement.dataset.build = 'vite';
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
} else {
    start();
}
