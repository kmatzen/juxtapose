import type { ErrorBanner } from './components/error-banner';
import type * as StudyState from './study-state';
import type { Lightbox } from './components/lightbox';
import type { RetakeModal } from './components/retake-modal';
import type { StimulusView } from './components/stimulus-view';
import type { ConditioningTiles } from './components/conditioning-tiles';
import type { TutorialBanner } from './components/tutorial-banner';

// Migration seam: what `script.js` still needs from code that already lives in components.
// Step 8 of docs/frontend-architecture.md deletes this file along with script.js.
export type SurveySeam = {
    /** The model the classic script calls; it has no module system of its own. */
    core: typeof StudyState;
    banner: ErrorBanner;
    lightbox: Lightbox;
    retake: RetakeModal;
    stimulus: StimulusView;
    conditioning: ConditioningTiles;
    /** Null when the page has no walkthrough: the submit gate must not fire for its absence. */
    tutorial: TutorialBanner | null;
};

declare global {
    interface Window {
        __JX__?: SurveySeam;
    }
}
