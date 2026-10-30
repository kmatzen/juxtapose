import { mountErrorBanner } from './components/error-banner';
import { mountLightbox } from './components/lightbox';
import { mountRetakeModal } from './components/retake-modal';
import { createTutorialBanner } from './components/tutorial-banner';
import type { TutorialBanner } from './components/tutorial-banner';
import { need } from './lib/dom';
import { createSurveyApi } from './lib/session-api';
import type { SurveyApi } from './lib/session-api';
import type { TutorialStep } from './study-state';
import type { SurveySeam } from './seam';
import { buildTutorialSteps } from './study-state';
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
        tutorial: mountTutorial(createSurveyApi(fetch)),
    };
}

function mountTutorial(api: SurveyApi): TutorialBanner | null {
    const banner = document.getElementById('tutorial-banner');
    if (!banner) return null;

    let steps: TutorialStep[] = [];
    const tutorial = createTutorialBanner(banner, {
        steps: () => steps,
        onComplete: () => document.dispatchEvent(new Event('jx:tutorial-complete')),
    });
    void api.config().then(({ ok, body }) => {
        // A config that will not load leaves the walkthrough unstarted: an empty one would gate Submit forever.
        if (!ok) return;
        steps = buildTutorialSteps(body);
        tutorial.start();
    });
    return tutorial;
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
