import type { Disposable } from '../lib/dom';
import { autofillDemographics, autofillSurvey } from '../lib/dev-autofill';
import type { SurveyApi, SurveyConfig } from '../lib/session-api';
import { buildResponses, buildSubmission, progressFrom } from '../study-state';
import type { Trial } from '../study-state';
import type { ConditioningTiles } from './conditioning-tiles';
import type { ErrorBanner } from './error-banner';
import type { QuestionFlow } from './question-flow';
import type { StimulusView } from './stimulus-view';
import type { TutorialBanner } from './tutorial-banner';

export type TrialRunnerProps = {
    api: SurveyApi;
    config: () => SurveyConfig | null;
    banner: ErrorBanner;
    stimulus: StimulusView;
    conditioning: ConditioningTiles;
    questions: QuestionFlow | null;
    tutorial: TutorialBanner | null;
    navigate: (url: string) => void;
    random?: () => number;
    now?: () => number;
    devAutofillDelayMs?: number;
    devSurveyDelayMs?: number;
};

export type TrialRunner = Disposable & {
    start(): Promise<void>;
    loadPair(index: number): Promise<void>;
    tilesSettled(ok: boolean): void;
    submit(event: Event): Promise<void>;
    index(): number;
};

const LOAD_FAILURE = 'Failed to load image pair. Please refresh the page.';
const LOAD_NETWORK = 'Network error. Please check your connection.';
const SUBMIT_NETWORK = 'Network error. Please check your connection and try again.';

/** The page lifecycle: who is in front (intake or survey), which pair is on screen, what Submit means. Components render; this decides what happens next. */
export function mountTrialRunner(host: HTMLElement, props: TrialRunnerProps): TrialRunner {
    const form = host.querySelector<HTMLFormElement>('#survey-form');
    const random = props.random ?? Math.random;
    const now = props.now ?? (() => Date.now());
    const timers: ReturnType<typeof setTimeout>[] = [];

    let trial: Trial | null = null;
    let current = 0;
    let pairStart: number | null = null;

    const devMode = () => !!props.config()?.dev_mode;
    const later = (fn: () => void, ms: number) => { timers.push(setTimeout(fn, ms)); };

    function showSection(id: string, hideId: string): void {
        host.querySelector(hideId)?.classList.remove('active');
        host.querySelector(id)?.classList.add('active');
    }

    function renderProgress(data: Trial, index: number): void {
        const progress = progressFrom(data, index);
        const currentEl = host.querySelector('#current-question');
        const totalEl = host.querySelector('#total-questions');
        const bar = host.querySelector<HTMLElement>('#progress-bar-fill');
        if (currentEl) currentEl.textContent = String(progress.current);
        if (totalEl) totalEl.textContent = String(progress.total);
        if (bar) bar.style.width = `${progress.percent}%`;

        if (index === 0) {
            const word = data.total_pairs === 1 ? 'pair' : 'pairs';
            const text = host.querySelector('#total-pairs-text');
            if (text) text.textContent = `You will see ${data.total_pairs} image ${word} in total.`;
        }
    }

    function autofillSurveySection(): void {
        const config = props.config();
        if (!config) return;
        // Programmatic checks fire no change event, so the Submit gate is re-run by hand.
        autofillSurvey(host, config, { random });
        props.questions?.validate();
    }

    async function loadPair(index: number): Promise<void> {
        let result: Awaited<ReturnType<SurveyApi['imagePair']>>;
        try {
            result = await props.api.imagePair(index);
        } catch (error) {
            props.banner.show(LOAD_NETWORK);
            console.error('Error:', error);
            return;
        }

        if (!result.ok) {
            // Nothing owed on this session: the index route serves the thank-you screen.
            if (result.status === 404) {
                props.navigate('/');
                return;
            }
            props.banner.show(LOAD_FAILURE);
            console.error('Error:', result.body.error);
            return;
        }

        const data = result.body;
        trial = data;
        current = index;
        await props.stimulus.show(data);
        renderProgress(data, index);

        form?.reset();
        props.conditioning.show(data);
        props.questions?.showTrial(data);

        if (devMode()) later(autofillSurveySection, props.devSurveyDelayMs ?? 100);
    }

    async function start(): Promise<void> {
        if (devMode()) {
            console.log('DEV MODE ENABLED - Forms will be auto-filled');
            if (host.querySelector('#demographics-form')) {
                later(() => {
                    const loaded = props.config();
                    if (loaded) autofillDemographics(host, loaded);
                }, props.devAutofillDelayMs ?? 500);
            }
        }

        const { ok, body, status } = await props.api.checkDemographics();
        if (!ok) {
            console.error('Error checking demographics:', status);
            return;
        }
        if (!body.submitted) return;

        // The server already left finished trials out of this session's list.
        showSection('#survey-section', '#demographics-section');
        const progress = host.querySelector<HTMLElement>('#survey-progress');
        if (progress) progress.style.display = 'block';
        await loadPair(0);
    }

    async function submit(event: Event): Promise<void> {
        event.preventDefault();

        if (props.tutorial) {
            // Best effort: the redirect is the point, and a failed write must not trap the participant.
            try {
                await props.api.completeTutorial();
            } catch (error) {
                console.error('Error:', error);
            }
            props.navigate('/');
            return;
        }

        if (!form || !trial) return;
        const fields: Record<string, string> = {};
        for (const [name, value] of new FormData(form).entries()) {
            if (typeof value === 'string') fields[name] = value;
        }
        const seconds = pairStart === null ? null : (now() - pairStart) / 1000;
        const responses = buildResponses(
            props.config()?.questions ?? [],
            fields,
            props.questions?.visibleSections() ?? [],
        );
        const payload = buildSubmission(trial, responses, seconds);

        let result: Awaited<ReturnType<SurveyApi['submitSurvey']>>;
        try {
            result = await props.api.submitSurvey(payload);
        } catch (error) {
            props.banner.show(SUBMIT_NETWORK);
            console.error('Error:', error);
            return;
        }

        if (result.ok && result.body.success) {
            if (result.body.completed) {
                props.navigate('/');
                return;
            }
            current += 1;
            await loadPair(current);
            window.scrollTo(0, 0);
            return;
        }

        props.banner.show('Failed to submit response. Please try again.');
        console.error('Error:', result.body.error);
    }

    const onSubmit = (event: Event) => { void submit(event); };
    form?.addEventListener('submit', onSubmit);

    return {
        start,
        loadPair,
        submit,
        index: () => current,
        tilesSettled(ok: boolean) {
            // Timing the pair from the tiles, not from the fetch: time on a spinner is not attention.
            if (ok) pairStart = now();
        },
        dispose() {
            for (const timer of timers.splice(0)) clearTimeout(timer);
            form?.removeEventListener('submit', onSubmit);
        },
    };
}
