import { mountDemographicsForm } from './components/demographics-form';
import { mountErrorBanner } from './components/error-banner';
import { mountLightbox } from './components/lightbox';
import { mountRetakeModal } from './components/retake-modal';
import { createTutorialBanner } from './components/tutorial-banner';
import type { TutorialBanner } from './components/tutorial-banner';
import { browserEnv, collectDeviceInfo } from './lib/device-info';
import { need } from './lib/dom';
import { createSurveyApi } from './lib/session-api';
import type { SurveyConfig } from './lib/session-api';
import type { TutorialStep } from './study-state';
import type { SurveySeam } from './seam';
import * as studyState from './study-state';
import { buildTutorialSteps } from './study-state';

type ConfigReady = (onReady: (config: SurveyConfig) => void) => void;

// Grows with each step of docs/frontend-architecture.md: the classic script's duties land here.
function mountSurveyPage(): SurveySeam {
    const api = createSurveyApi(fetch);
    const banner = mountErrorBanner(document.body, {
        activeSection: () => document.querySelector<HTMLElement>('.section.active'),
    });
    const retake = mountRetakeModal(document.body);

    let config: SurveyConfig | null = null;
    const waiting: ((config: SurveyConfig) => void)[] = [];
    const onConfig: ConfigReady = (onReady) => {
        if (config) onReady(config);
        else waiting.push(onReady);
    };

    void api.config().then(({ ok, body }) => {
        // A config that will not load leaves the walkthrough unstarted: an empty one gates Submit forever.
        if (!ok) return;
        config = body;
        for (const ready of waiting.splice(0)) ready(body);
    });

    const form = document.getElementById('demographics-form');
    if (form) {
        mountDemographicsForm(form as HTMLFormElement, {
            api,
            banner,
            retake,
            // Boot-time snapshot, as the legacy page did: a mid-form viewport change must not split a row.
            deviceInfo: collectDeviceInfo(browserEnv()),
            checkboxFields: () =>
                (config?.demographics ?? []).filter((f) => f.type === 'checkbox').map((f) => f.name),
            onAccepted: () => {
                window.location.href = '/';
            },
            onDeclinedRetake: () => {
                window.location.reload();
            },
        });
    }

    return {
        core: studyState,
        banner,
        lightbox: mountLightbox(need(document.body, '#image-lightbox')),
        retake,
        tutorial: mountTutorial(document.getElementById('tutorial-banner'), onConfig),
    };
}

/** Steps come from config, so the banner is built before the read and starts when the read lands. */
function mountTutorial(
    banner: HTMLElement | null,
    onConfig: ConfigReady,
): TutorialBanner | null {
    if (!banner) return null;

    let steps: TutorialStep[] = [];
    const tutorial = createTutorialBanner(banner, {
        steps: () => steps,
        onComplete: () => document.dispatchEvent(new Event('jx:tutorial-complete')),
    });
    onConfig((loaded) => {
        steps = buildTutorialSteps(loaded);
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
