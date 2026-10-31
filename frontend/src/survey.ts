import { mountDemographicsForm } from './components/demographics-form';
import { mountDevBadge, mountDevicePanel } from './components/device-panel';
import { mountTrialRunner } from './components/trial-runner';
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
import * as studyState from './study-state';
import { buildTutorialSteps } from './study-state';

type ConfigReady = (onReady: (config: SurveyConfig) => void) => void;

// Grows with each step of docs/frontend-architecture.md: the classic script's duties land here.
function mountSurveyPage(): void {
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

    // A config that never loads leaves the walkthrough unstarted and the questions unbuilt: say so, and take one more shot.
    const readConfig = async (retries: number): Promise<void> => {
        let loaded = null;
        try {
            const { ok, body } = await api.config();
            if (ok) loaded = body;
        } catch {
            // A read that never lands is the same outage to the participant as a 500.
        }
        if (loaded) {
            banner.hide();
            config = loaded;
            studyConfig = loaded;
            for (const ready of waiting.splice(0)) ready(loaded);
            return;
        }
        banner.show(CONFIG_FAILURE);
        if (retries > 0) setTimeout(() => { void readConfig(retries - 1); }, CONFIG_RETRY_MS);
    };
    void readConfig(1);

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
    mountDevicePanel(document.body, () => browserEnv()).render();

    // The question block asks the tiles whether this pair can be answered, so the tiles mount first.
    const stimulus = mountStimulusView(document.body, {
        lightbox,
        banner,
        onBlockingChange: blockForm,
        onSettled: (ok) => runner?.tilesSettled(ok),
    });

    // Pages that carry no question block (thank you, admin) mount no flow.
    const surveySection = document.getElementById('survey-section');
    const questions = surveySection && mountQuestionFlow(surveySection, {
        form: need(document, '#survey-form') as HTMLFormElement,
        submitButton: need(document, '#submit-btn') as HTMLButtonElement,
        blocksSubmit: () => (!!tutorial && !tutorial.isComplete()) || stimulus.failed(),
        blockReason: () => stimulus.failed() ? STIMULUS_FAILURE : 'Complete the tutorial first',
        questions: () => studyConfig?.questions ?? [],
        inputs: () => studyConfig?.inputs ?? [],
        observeSections: (sections, onVisible) =>
            observeSectionsIn(surveySection.querySelector('.questions-container'), sections, onVisible),
    });

    const conditioning = mountConditioningTiles(document.body, {
        lightbox,
        galleryInput: () => inputOfType('image_gallery'),
        maskInput: () => inputOfType('image'),
        outputImages: outputTiles,
        tapThresholdPx: TAP_THRESHOLD_PX,
    });

    // The runner is the last thing mounted and the first thing started: it needs every component.
    const runner = mountTrialRunner(document.body, {
        api,
        config: () => studyConfig,
        banner,
        stimulus,
        conditioning,
        questions,
        tutorial,
        navigate: (url) => { window.location.href = url; },
    });

    onConfig((loaded) => {
        mountDevBadge(document.body, loaded);
        void runner.start();
    });

}


const TAP_THRESHOLD_PX = 10;
const CONFIG_FAILURE = 'Failed to load the study setup. Please refresh the page.';
const STIMULUS_FAILURE = 'The images did not load. Refresh the page to answer this pair.';
const CONFIG_RETRY_MS = 2000;
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
    mountSurveyPage();
    document.documentElement.dataset.build = 'vite';
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
} else {
    start();
}
