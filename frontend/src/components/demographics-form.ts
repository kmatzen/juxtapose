import type { Disposable } from '../lib/dom';
import type { ErrorBanner } from './error-banner';
import type { DemographicsPayload, SurveyApi } from '../lib/session-api';
import type { DeviceInfo } from '../lib/device-info';
import type { RetakeModal } from './retake-modal';
import { normalizeDemographics } from '../study-state';

export type DemographicsFormProps = {
    api: SurveyApi;
    banner: ErrorBanner;
    retake: RetakeModal;
    deviceInfo: DeviceInfo;
    /** Checkbox field names, read at submit: the study config may not have arrived yet. */
    checkboxFields: () => string[];
    /** Navigation belongs to the page, not to a form. */
    onAccepted: () => void;
    onDeclinedRetake: () => void;
};

export type DemographicsForm = Disposable;

const FAILURE = 'Failed to submit demographics. Please try again.';
const NETWORK = 'Network error. Please check your connection and try again.';

/** Wires the server-rendered intake form: serialise, post, settle the retake decision, navigate. Its markup stays in the template, which renders the fields from the study config. */
export function mountDemographicsForm(form: HTMLFormElement, props: DemographicsFormProps): DemographicsForm {
    let inFlight = false;

    const post = (payload: DemographicsPayload) => props.api.submitDemographics(payload);

    async function submit(event: Event): Promise<void> {
        event.preventDefault();
        // The button is disabled while a post is open, but Enter on the last field bypasses that.
        if (inFlight) return;
        inFlight = true;
        const submitButton = form.querySelector<HTMLButtonElement>('button[type="submit"]');
        if (submitButton) submitButton.disabled = true;
        try {
            // No file inputs in this form; FormData's entry type allows File for forms in general.
            const entries = Array.from(new FormData(form).entries()) as [string, string][];
            const payload: DemographicsPayload = {
                ...normalizeDemographics(entries, props.checkboxFields()),
                device_info: props.deviceInfo,
            };

            let reply = await post(payload);
            if (reply.ok && reply.body.success) {
                if (reply.body.is_retaking) {
                    if (!(await props.retake.ask())) {
                        props.onDeclinedRetake();
                        return;
                    }
                    reply = await post({ ...payload, confirm_retake: true });
                }
                if (reply.ok && reply.body.success) {
                    props.onAccepted();
                    return;
                }
                props.banner.show(FAILURE);
                return;
            }
            props.banner.show(FAILURE);
        } catch {
            props.banner.show(NETWORK);
        } finally {
            inFlight = false;
            if (submitButton) submitButton.disabled = false;
        }
    }

    form.addEventListener('submit', submit);
    return {
        dispose() {
            form.removeEventListener('submit', submit);
        },
    };
}
