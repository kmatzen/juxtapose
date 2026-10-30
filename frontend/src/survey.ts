import { mountDemographicsForm } from './components/demographics-form';
import { mountErrorBanner } from './components/error-banner';
import { mountLightbox } from './components/lightbox';
import { mountRetakeModal } from './components/retake-modal';
import { mountQuestionFlow, observeSectionsIn } from './components/question-flow';
import { mountStimulusView } from './components/stimulus-view';
import { mountConditioningTiles } from './components/conditioning-tiles';
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
        studyConfig = body;
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

    const lightbox = mountLightbox(need(document.body, '#image-lightbox'));
    const tutorial = mountTutorial(document.getElementById('tutorial-banner'), onConfig);

    // Pages that carry no question block (thank you, admin) mount no flow.
    const surveySection = document.getElementById('survey-section');
    const questions = surveySection && mountQuestionFlow(surveySection, {
        form: need(document, '#survey-form') as HTMLFormElement,
        submitButton: need(document, '#submit-btn') as HTMLButtonElement,
        blocksSubmit: () => !!tutorial && !tutorial.isComplete(),
        questions: () => studyConfig?.questions ?? [],
        inputs: () => studyConfig?.inputs ?? [],
        observeSections: (sections, onVisible) =>
            observeSectionsIn(surveySection.querySelector('.questions-container'), sections, onVisible),
    });

    return {
        core: studyState,
        banner,
        lightbox,
        retake,
        stimulus: mountStimulusView(document.body, {
            lightbox,
            banner,
            onBlockingChange: blockForm,
            onSettled: (ok) => document.dispatchEvent(new CustomEvent('jx:stimulus-settled', { detail: { ok } })),
            // The conditioning tiles are still script.js; step 6 moves them behind this event.
            onTrial: (trial) => document.dispatchEvent(new CustomEvent('jx:trial-loaded', { detail: trial })),
        }),
        conditioning: mountConditioningTiles(document.body, {
            lightbox,
            galleryInput: () => inputOfType('image_gallery'),
            maskInput: () => inputOfType('image'),
            outputImages: outputTiles,
            tapThresholdPx: TAP_THRESHOLD_PX,
        }),
        questions,
        tutorial,
    };
}

const TAP_THRESHOLD_PX = 10;
let studyConfig: SurveyConfig | null = null;

function inputOfType(type: string) {
    return studyConfig?.inputs?.find((input) => input.type === type) ?? null;
}

/** Output tiles are found by the config's output names, with the legacy ID fallback per output. */
function outputTiles(): HTMLImageElement[] {
    const found: HTMLImageElement[] = [];
    for (const output of (studyConfig?.outputs ?? []).filter((o) => o.type === 'image')) {
        for (const [suffix, fallback] of [['a', 'image-a'], ['b', 'image-b']] as const) {
            const image = (document.getElementById(`output-${output.name}-${suffix}`)
                ?? document.getElementById(fallback)) as HTMLImageElement | null;
            if (image) found.push(image);
        }
    }
    if (found.length) return found;
    return ['image-a', 'image-b']
        .map((id) => document.getElementById(id))
        .filter((image): image is HTMLImageElement => !!image);
}

/** The legacy page blocks the form with inline styles; the tiles decide when, the form decides how. */
function blockForm(blocked: boolean): void {
    const form = document.getElementById('survey-form') as HTMLElement | null;
    if (!form) return;
    form.style.pointerEvents = blocked ? 'none' : 'auto';
    form.style.opacity = blocked ? '0.5' : '1';
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
