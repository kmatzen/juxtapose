import type { ErrorBanner } from './components/error-banner';
import type * as StudyState from './study-state';
import type { Lightbox } from './components/lightbox';
import type { RetakeModal } from './components/retake-modal';

// Migration seam: what `script.js` still needs from code that already lives in components.
// Step 8 of docs/frontend-architecture.md deletes this file along with script.js.
export type SurveySeam = {
    /** The model the classic script calls; it has no module system of its own. */
    core: typeof StudyState;
    banner: ErrorBanner;
    lightbox: Lightbox;
    retake: RetakeModal;
};

declare global {
    interface Window {
        __JX__?: SurveySeam;
    }
}
